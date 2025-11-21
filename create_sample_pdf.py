"""Quick script to create sample PDF for testing ingestion."""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def create_sample():
    c = canvas.Canvas('data/raw_files/sample_thai.pdf', pagesize=A4)
    
    # Page 1
    c.setFont('Helvetica', 16)
    c.drawString(50, 800, 'Sample PDF Document for Ingestion Testing')
    c.setFont('Helvetica', 12)
    c.drawString(50, 770, 'This is a test document with English text.')
    c.drawString(50, 750, 'Page 1 content for OCR and chunking pipeline.')
    c.drawString(50, 730, 'Numbers: 1234567890')
    c.drawString(50, 710, 'Email: test@example.com')
    c.drawString(50, 690, 'Phone: 081-234-5678')
    
    # Page 2
    c.showPage()
    c.setFont('Helvetica', 16)
    c.drawString(50, 800, 'Page 2: Additional Test Content')
    c.setFont('Helvetica', 12)
    c.drawString(50, 770, 'Multi-page PDF testing for ingestion service.')
    c.drawString(50, 750, 'This should create separate page records.')
    c.drawString(50, 730, 'The chunking system will segment this content.')
    
    c.save()
    print('Created data/raw_files/sample_thai.pdf successfully!')

if __name__ == '__main__':
    create_sample()
