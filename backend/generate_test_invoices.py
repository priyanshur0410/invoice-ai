"""
Generates sample test invoice text files for validation.
Run: python generate_test_invoices.py
Creates: test_data/ folder with 3 sample invoice text files
"""
import os

os.makedirs("test_data", exist_ok=True)

# Sample 1: Standard US Invoice
INVOICE_1 = """
TECHCORP SOLUTIONS INC.
123 Silicon Valley Blvd, San Jose, CA 95110
Phone: (408) 555-0192  |  Email: billing@techcorp.com

                                        INVOICE

Invoice Number:  TC-2024-0891
Invoice Date:    March 15, 2024
Due Date:        April 14, 2024
Payment Terms:   Net 30

Bill To:
---------
Acme Corporation
456 Business Park Dr
New York, NY 10001
Attn: Accounts Payable

DESCRIPTION                          QTY    UNIT PRICE      AMOUNT
-------------------------------------------------------------------
Cloud Infrastructure Services         1      $2,500.00     $2,500.00
Software License (Annual)             3        $450.00     $1,350.00
Technical Support Package             1        $800.00       $800.00
API Integration Consulting           10        $150.00     $1,500.00
-------------------------------------------------------------------
                                              Subtotal:    $6,150.00
                                              Tax (8.5%):    $522.75
                                              Discount:      -$50.00
                                              TOTAL DUE:   $6,622.75

Payment Methods: Bank Transfer / Credit Card
Bank: First National Bank  |  Account: 123-456-789  |  Routing: 021000021

Thank you for your business!
"""

# Sample 2: Indian GST Invoice
INVOICE_2 = """
INFOSYS DIGITAL SERVICES LTD
Registered Office: Electronics City, Bangalore - 560100
GSTIN: 29AABCI1681G1ZN  |  PAN: AABCI1681G

                    TAX INVOICE

Invoice No:     INF/2024/Q4/2847
Invoice Date:   15-Jan-2024
Due Date:       14-Feb-2024

Bill To:                            Ship To:
Tata Consultancy Ltd               Tata Consultancy Ltd
Nariman Point, Mumbai 400021       Whitefield, Bangalore 560066
GSTIN: 27AABCT3518Q1Z8

HSN     DESCRIPTION                    QTY   RATE (INR)    AMOUNT
-------------------------------------------------------------------
998314  Software Development Services   80 hrs  1,200.00    96,000.00
998313  UI/UX Design Services           20 hrs    900.00    18,000.00
998315  Quality Assurance               30 hrs    750.00    22,500.00
-------------------------------------------------------------------
                                        Taxable Value:    1,36,500.00
                                        CGST @ 9%:           12,285.00
                                        SGST @ 9%:           12,285.00
                                        TOTAL:             1,61,070.00

Amount in Words: One Lakh Sixty-One Thousand Seventy Rupees Only

Bank Details: HDFC Bank  |  A/C: 50100234567891  |  IFSC: HDFC0001234
"""

# Sample 3: EU Invoice (EUR)
INVOICE_3 = """
MÜNCHEN AUTOMOTIVE GMBH
Leopoldstrasse 42, 80802 München, Deutschland
USt-IdNr.: DE123456789  |  Tel: +49 89 1234567

                    RECHNUNG / INVOICE

Rechnungsnummer:    MUC-2024-0156
Rechnungsdatum:     2024-02-20
Fälligkeitsdatum:   2024-03-21
Zahlungsbedingungen: 30 Tage netto

Rechnungsempfänger:
BMW Group AG
Petuelring 130
80788 München

POS   BESCHREIBUNG / DESCRIPTION          MENGE   EP (EUR)   GESAMT (EUR)
--------------------------------------------------------------------------
1     Precision Engineering Consultation      5h    450.00      2,250.00
2     CAD Software License                    2     1,200.00    2,400.00
3     Technical Documentation                 1     850.00        850.00
4     Project Management                     10h    200.00      2,000.00
--------------------------------------------------------------------------
                                         Nettobetrag:          7,500.00
                                         MwSt. 19%:            1,425.00
                                         Rechnungsbetrag:      8,925.00

IBAN: DE89 3704 0044 0532 0130 00  |  BIC: COBADEFFXXX
"""

test_files = {
    "test_data/invoice_techcorp_us.txt": INVOICE_1,
    "test_data/invoice_infosys_india.txt": INVOICE_2,
    "test_data/invoice_munchen_eu.txt": INVOICE_3,
}

for path, content in test_files.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"Created: {path}")

print("\nTest invoices generated in test_data/")
print("Use these as OCR input for local testing, or convert to PDF/image.")
