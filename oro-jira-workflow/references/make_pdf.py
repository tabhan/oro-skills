from fpdf import FPDF
from PIL import Image
import os

DIR = "/opt/projects/buckman/var/buc-856-test"
OUT = "/mnt/e/tmp/BUC-856-test-report.pdf"

pages = [
    ("Default landing page list - new CREATED AT and UPDATED AT columns; default sort Updated At DESC", "01-default-list.png"),
    ("Sorted by Created At ascending (oldest first)", "02-sorted-created-asc.png"),
    ("Sorted by Created At descending (second click on header)", "03-sorted-created-desc.png"),
    ("Sorted by Updated At ascending", "05-sorted-updated-asc.png"),
    ("Sorted by Updated At descending", "06-sorted-updated-desc.png"),
    ("Grid Settings -> Filters tab shows new Created At / Updated At filters", "04-grid-settings-filters.png"),
]

pdf = FPDF(orientation="P", unit="mm", format="A4")
pdf.set_auto_page_break(auto=False)

# Cover
pdf.add_page()
pdf.set_font("Helvetica", "B", 18)
pdf.cell(0, 12, "BUC-856 Test Report", ln=1)
pdf.set_font("Helvetica", "", 11)
pdf.cell(0, 7, "Landing Pages: Search & Sort", ln=1)
pdf.ln(4)
pdf.set_font("Helvetica", "", 10)
meta = [
    "Ticket: BUC-856 - Landing pages: difficult to find without search/sort options",
    "Branch: feature/BUC-856-landing-pages---difficult-to-fin",
    "Date:   2026-04-25",
    "Tester: Tab Han (automated via Chrome DevTools MCP)",
    "Env:    https://local.aaxisdev.net/control-center/",
]
for m in meta:
    pdf.cell(0, 6, m, ln=1)

pdf.ln(4)
pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 7, "Acceptance Criteria", ln=1)
pdf.set_font("Helvetica", "", 10)
acs = [
    ("AC1", "Search by title (partial+full)", "Added title string filter to cms-page-grid", "PASS"),
    ("AC3", "Sort by Created Date asc/desc with indicator", "Added createdAt column, sorter, datetime filter", "PASS"),
    ("AC4", "Sort by Modified Date asc/desc with indicator", "Added updatedAt column, sorter, datetime filter; default Updated At DESC", "PASS"),
]
pdf.set_fill_color(230, 236, 245)
pdf.cell(15, 7, "AC", border=1, fill=True)
pdf.cell(70, 7, "Requirement", border=1, fill=True)
pdf.cell(80, 7, "Implementation", border=1, fill=True)
pdf.cell(20, 7, "Result", border=1, ln=1, fill=True)
for ac, req, impl, res in acs:
    pdf.cell(15, 14, ac, border=1)
    x, y = pdf.get_x(), pdf.get_y()
    pdf.multi_cell(70, 7, req, border=1)
    pdf.set_xy(x + 70, y)
    pdf.multi_cell(80, 7, impl, border=1)
    pdf.set_xy(x + 150, y)
    pdf.cell(20, 14, res, border=1, ln=1)

pdf.ln(4)
pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 7, "Behat Coverage", ln=1)
pdf.set_font("Helvetica", "", 10)
pdf.cell(0, 6, "src/Buckman/Bundle/CMSBundle/Tests/Behat/Features/landing_page_search_sort.feature", ln=1)
for s in ["Filter landing pages by title keyword (AC1)",
          "Sort by Created At ascending then descending (AC3)",
          "Sort by Updated At ascending then descending (AC4)",
          "Default landing page list is sorted by Updated At descending"]:
    pdf.cell(0, 6, "  * " + s, ln=1)

pdf.ln(2)
pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 7, "Files Changed", ln=1)
pdf.set_font("Courier", "", 9)
for f in ["src/Buckman/Bundle/CMSBundle/Resources/config/oro/datagrids.yml",
          "src/Buckman/Bundle/CMSBundle/Tests/Behat/Features/landing_page_search_sort.feature"]:
    pdf.cell(0, 5, f, ln=1)

# Screenshot pages
for i, (caption, fname) in enumerate(pages, 1):
    path = os.path.join(DIR, fname)
    if not os.path.exists(path):
        continue
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, f"Fig {i} - {caption}", ln=1)
    img = Image.open(path)
    iw, ih = img.size
    page_w = pdf.w - 20
    page_h = pdf.h - 30
    ratio = min(page_w / iw, page_h / ih)
    w = iw * ratio
    h = ih * ratio
    pdf.image(path, x=(pdf.w - w) / 2, y=20, w=w, h=h)

pdf.output(OUT)
print("Wrote", OUT)
