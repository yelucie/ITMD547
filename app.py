from flask import Flask, render_template, request, redirect, url_for, g
from dotenv import load_dotenv
import openai
import PyPDF2
import logging
import os
import sqlite3
import hashlib

class PDFSummarizer:
    def __init__(self, database="summaries.db", openai_key=None):
        # Initialize Flask app and database configurations
        self.app = Flask(__name__)
        self.DATABASE = database
        load_dotenv()
        openai.api_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.bind_routes()  # Setup URL routes for the application

    def get_db(self):
        # Method to get the database connection
        db = getattr(g, "_database", None)
        if db is None:
            db = g._database = sqlite3.connect(self.DATABASE)
        return db

    def close_connection(self, exception):
        # Method to close the database connection
        db = getattr(g, "_database", None)
        if db is not None:
            db.close()

    def init_db(self):
        # Initialize the database by creating tables as per the schema
        with self.app.app_context():
            db = self.get_db()
            with self.app.open_resource("schema.sql", mode="r") as f:
                db.cursor().executescript(f.read())
            db.commit()

    def extract_text_from_pdf(self, pdf_file):
        # Extract the text from the PDF
        extracted_text = ""

        try:
            reader = PyPDF2.PdfReader(pdf_file)

            # Loop through all pages
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                extracted_text += page_text

        except Exception as e:
            # Handle the PyPDF2 exception
            logging.error(f"A PdfReader error occured: {e}")
            raise ValueError("An error occurred while reading the PDF.")

        return extracted_text

    def openai_summarization(self, text):
        # Use the OpenAI API to send the text
        api_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides summaries."},
                {"role": "user", "content": f"Provide a detailed summary of the following text:\n{text}"},
            ],
            temperature=0.5,
            stop=None,
            timeout=30
        )

        # Return the response from the API
        summarized_text = api_response["choices"][0]["message"]["content"]
        return summarized_text

    def retrieve_summary(self, text, pdf_hash):
        # Save and / or retrieve the summary
        try:
            # Check for an existing summary in the database using the PDF's hash
            db = self.get_db()
            existing_pdf = db.execute("SELECT summary FROM summaries WHERE pdf_hash=?", (pdf_hash,))
            summary = existing_pdf.fetchone()

            # If it exists, use it
            if summary:
                summary = summary[0]
            # If not, generate a new summary, store it, and then use it
            else:
                summary = self.openai_summarization(text)
                db.execute("INSERT INTO summaries (pdf_hash, summary) VALUES (?, ?)",(pdf_hash, summary))
                db.commit()
                
        except TimeoutError as e:
            # Handle the timeout error
            logging.error(f"A OpenAI summarization error occured: {e}")
            raise TimeoutError("The summarization process timed out. Please try again later.")

        except sqlite3.Error as e:
            # Handle SQLite database errors
            logging.error(f"A database error occured: {e}")
            raise sqlite3.Error("An error occurred with the database.")
        
        except Exception as e:
            # Handle other unforeseen exceptions
            logging.error(f"An error occured: {e}")
            raise Exception("An error occured while retrieving the summary.")

        return summary

    def bind_routes(self):
        # Define URL routes and their corresponding handlers

        @self.app.route("/", methods=["GET"])
        def index():
            # Render the file upload page
            return render_template("upload.html")

        @self.app.route("/upload", methods=["POST"])
        def upload_file():
            # Handle file upload and process the PDF
            uploaded_file = request.files["file"]

            # Check if the file has the correct type
            if uploaded_file.filename == "" or not uploaded_file.filename.endswith(".pdf"):
                return render_template("upload.html", error="Please ensure that the uploaded file is in PDF format.")
            
            try:
                # Get the PDF hash
                text = self.extract_text_from_pdf(uploaded_file)
                pdf_hash = hashlib.sha256(text.encode()).hexdigest()
                
                # Get the PDF's summary
                summary = self.retrieve_summary(text, pdf_hash)
                return render_template("summary.html", summary=summary)

            except Exception as e:
                return render_template("upload.html", error=str(e))

        @self.app.teardown_appcontext
        def close_connection(exception):
            # Ensure database connection is closed after request is complete
            self.close_connection(exception)


if __name__ == "__main__":
    # Run the Flask application
    app = PDFSummarizer()
    if not os.path.exists("summaries.db"):
        app.init_db()
    app.app.run(debug=True)