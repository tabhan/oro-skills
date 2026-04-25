from fpdf import FPDF
from PIL import Image
import os

DIR = "/opt/projects/buckman/var/buc-856-test"
OUT = "/mnt/e/tmp/BUC-856-test-report.pdf"

pages = [
    ("Default landing page list - new CREATED AT and UPDATED AT columns visible. Default sort: Updated At DESC. Title chip available at top.", "01-default.png"),
    ("AC1 - Title filter: 'contains Smart Technology' narrows 1237 records to 3. Visible Title column on every row contains the keyword.", "02-title-filter.png"),
    ("AC3/AC4 - Sort by Created At ascending (oldest first). Sort indicator on column header. Updated At sorting works the same way.", "03-sort-created.png"),
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
for m in [
    "Ticket: BUC-856 - Landing pages: difficult to find without search/sort options",
    "Branch: feature/BUC-856-landing-pages---difficult-to-fin",
    "Date:   2026-04-25",
    "Tester: Tab Han (automated via Chrome DevTools MCP)",
    "Env:    https://local.aaxisdev.net/control-center/",
]:
    pdf.cell(0, 6, m, ln=1)

pdf.ln(3)
pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 7, "Acceptance Criteria", ln=1)
pdf.set_font("Helvetica", "", 10)
pdf.set_fill_color(230, 236, 245)
pdf.cell(15, 7, "AC", border=1, fill=True)
pdf.cell(70, 7, "Requirement", border=1, fill=True)
pdf.cell(80, 7, "Implementation", border=1, fill=True)
pdf.cell(20, 7, "Result", border=1, ln=1, fill=True)
for ac, req, impl, res in [
    ("AC1", "Search by title (partial+full)",
     "titleSearch filter on pageTitle.string; join restricted to default fallback title (pageTitle.localization IS NULL)",
     "PASS"),
    ("AC3", "Sort by Created Date asc/desc with indicator",
     "createdAt column + sorter on page.createdAt + datetime filter",
     "PASS"),
    ("AC4", "Sort by Modified Date asc/desc with indicator",
     "updatedAt column + sorter on page.updatedAt + datetime filter; default sort updatedAt DESC",
     "PASS"),
]:
    pdf.cell(15, 18, ac, border=1)
    x, y = pdf.get_x(), pdf.get_y()
    pdf.multi_cell(70, 6, req, border=1)
    pdf.set_xy(x + 70, y)
    pdf.multi_cell(80, 6, impl, border=1)
    pdf.set_xy(x + 150, y)
    pdf.cell(20, 18, res, border=1, ln=1)

pdf.ln(3)
pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 7, "Known limitation", ln=1)
pdf.set_font("Helvetica", "", 10)
pdf.multi_cell(0, 5,
    "The Title filter searches the DEFAULT (fallback) title only. If an admin user "
    "has a non-default localization (e.g., es_CA) and the page has a Spanish title, "
    "the Title column displays the Spanish text but the filter still matches on the "
    "default title. This mirrors how Oro itself handles localized search on the "
    "Product grid (denormalizedDefaultName). True 'search what you see' would "
    "require either (a) a per-request BuildBefore listener that injects the current "
    "localization id into the join condition, or (b) denormalizing the localized "
    "title onto a scalar column with an entity listener. Out of scope for BUC-856.")

pdf.ln(2)
pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 7, "Behat coverage", ln=1)
pdf.set_font("Helvetica", "", 10)
pdf.cell(0, 6, "src/Buckman/Bundle/CMSBundle/Tests/Behat/Features/landing_page_search_sort.feature", ln=1)
for s in ["Filter landing pages by title keyword (AC1)",
          "Sort by Created At ascending then descending (AC3)",
          "Sort by Updated At ascending then descending (AC4)",
          "Default landing page list is sorted by Updated At descending"]:
    pdf.cell(0, 5, "  * " + s, ln=1)

pdf.ln(2)
pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 7, "Files changed", ln=1)
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
    pdf.multi_cell(0, 6, f"Fig {i} - {caption}")
    img = Image.open(path)
    iw, ih = img.size
    page_w = pdf.w - 20
    page_h = pdf.h - 35
    ratio = min(page_w / iw, page_h / ih)
    w = iw * ratio
    h = ih * ratio
    pdf.image(path, x=(pdf.w - w) / 2, y=pdf.get_y() + 4, w=w, h=h)

pdf.output(OUT)
print("Wrote", OUT)
