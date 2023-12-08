import unittest
import os
import tempfile
import hashlib
from flask_testing import TestCase
from app import PDFSummarizer

class FlaskAppTestCase(TestCase):
    TESTING = True

    def create_app(self):
        # Create a temporary database for testing
        db_fd, db_path = tempfile.mkstemp()
        self.db_fd = db_fd
        self.db_path = db_path

        self.flask_app = PDFSummarizer(database=db_path)
        self.flask_app.app.config['TESTING'] = True
        return self.flask_app.app

    def setUp(self):
        # Set up the test client and initialize the database
        self.app = self.create_app().test_client()
        with self.flask_app.app.app_context():
            self.flask_app.init_db()

    def tearDown(self):
        # Close and remove the temporary database
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def upload_file(self, filename):
        # Helper function to simulate file upload
        try:
            with open(filename, 'rb') as f:
                data = {'file': (f, os.path.basename(filename))}
                return self.app.post('/upload', data=data, content_type='multipart/form-data')
        except FileNotFoundError:
            return None
        
    def get_text(self, file_path):
        # Helper function to get file hash
        try:
            with open(file_path, 'rb') as file:
                text = self.flask_app.extract_text_from_pdf(file)
        except FileNotFoundError:
            return None
        return text
    
    def get_pdf_hash(self, text):
        pdf_hash = hashlib.sha256(text.encode()).hexdigest()
        return pdf_hash

    # Complete Test Case for PDF Upload
    def test_pdf_upload(self):
        response = self.upload_file('test_data/sample.pdf')
        self.assertEqual(response.status_code, 200)

        response = self.upload_file('test_data/sample.txt')
        if response:
            self.assertNotEqual(response.status_code, 200)

    # Placeholder for Summary Generation Test
    def test_summary_generation(self):
        file_path = 'test_data/sample.pdf'
        
        # Upload the PDF
        response = self.upload_file(file_path)
        self.assertEqual(response.status_code, 200)
        
        # Get the PDF hash
        text = self.get_text(file_path)
        pdf_hash = self.get_pdf_hash(text)
        
        # Check the generated summary in the database
        with self.flask_app.app.app_context():
            db = self.flask_app.get_db()
            result = db.execute("SELECT summary FROM summaries WHERE pdf_hash=?", (pdf_hash,)).fetchone()
            summary = result[0]
            
        # Check if the keywords are present in the generated text
        keywords = ["undergraduate", "final", "project", "flask", "python", "web", "application", "openai"]
        for keyword in keywords:
            self.assertIn(keyword, summary.lower(), f"{keyword} not found in the summmarized text.")
                
    # Placeholder for Exception Handling Test
    def test_exception_handling(self):
        # TODO: Implement a test to check how the application handles exceptions.
        # Consider scenarios such as uploading an invalid file or causing an internal error.
        pass
        
    # Database Cache Test Case
    def test_database_cache(self):
        file_path = 'test_data/sample.pdf'
        
        # Upload the same file twice    
        response1 = self.upload_file(file_path)
        response2 = self.upload_file(file_path)

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        
        # Get the PDF hash
        text = self.get_text(file_path)
        pdf_hash = self.get_pdf_hash(text)

        # Check that the database has only one instance of the file
        with self.flask_app.app.app_context():
            db = self.flask_app.get_db()
            result = db.execute("SELECT COUNT(*) FROM summaries WHERE pdf_hash=?", (pdf_hash,)).fetchone()
            count = result[0]

        self.assertEqual(count, 1)

if __name__ == '__main__':
    unittest.main()