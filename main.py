
import fitz
import sys
import re
import pdftotext

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QStatusBar, QHeaderView, QAction
)
from PyQt5.QtCore import Qt

def extract_links(pdf_path: str) -> dict:
    """
    Return a mapping of anchor text → URL for every URI link annotation in the PDF.
    """
    link_map = {}
    doc = fitz.open(pdf_path)
    for page in doc:
        for link in page.get_links():
            uri = link.get("uri", None)
            if not uri:
                continue
            rect = fitz.Rect(link["from"])
            anchor = page.get_text("text", clip=rect).strip()
            if anchor:
                link_map[anchor] = uri
    return link_map

def parse_resume(pdf_path: str) -> dict:
    """
    Parse a resume PDF into a nested dictionary structure,
    but first replace any hyperlink anchor text with its URL.
    """
    try:
        link_map = extract_links(pdf_path)
    except Exception as e:
        link_map = {}
        print(f"Warning: could not extract hyperlinks: {e}", file=sys.stderr)

    with open(pdf_path, "rb") as f:
        pdf = pdftotext.PDF(f)

    raw_text = ("\n\n\n\n\n".join(pdf)
                .replace("\u200b", "")
                .replace("\x0c", ""))

    for anchor, uri in link_map.items():
        if uri.startswith("mailto:") or uri.startswith("tel:"):
            uri = uri.split(":")[1]
        raw_text = raw_text.replace(anchor, f"{uri}")

    paragraphs = [p for p in raw_text.split("\n\n") if p.strip()]

    header_lines = []
    for para in paragraphs[:5]:
        for line in para.splitlines():
            text = line.strip()
            if text:
                header_lines.append(text)
    sections = {"Header": header_lines}

    for para in paragraphs[5:]:
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        if not lines:
            continue
        section_title = lines[0]
        content_lines = lines[1:]

        if section_title.lower() == "skills":
            skills = {}
            for line in content_lines:
                if ":" in line:
                    key, vals = line.split(":", 1)
                    skills[key.strip()] = [v.strip() for v in vals.split(",") if v.strip()]
            sections[section_title] = skills
            continue

        subsection_entries = {}
        current_entry = None
        last_bullet_idx = None

        for line in content_lines:
            if section_title == "Education" and "|" in line:
                left, date_part = line.split("|", 1)
                left = left.strip()
                date_part = date_part.strip()
                name_place, *rest = [p.strip() for p in left.split("—", 1)]
                entry = {}
                if rest:
                    deg_major = rest[0]
                    deg_parts = [x.strip() for x in deg_major.split(",", 1)]
                    entry["Degree type"] = deg_parts[0]
                    if len(deg_parts) > 1:
                        entry["Major"] = deg_parts[1]
                dates = re.split(r"\s*-\s*", date_part)
                entry["Date start"] = dates[0]
                entry["Date end"] = dates[1] if len(dates) > 1 else dates[0]
                entry["Data"] = []
                subsection_entries[name_place] = entry
                current_entry = entry
                last_bullet_idx = None
                continue

            if "|" in line:
                parts = re.split(r"\s*(,|—|\|)\s*", line)
                name = parts[0].strip()
                entry = {}
                for delim, txt in zip(parts[1::2], parts[2::2]):
                    txt = txt.strip()
                    if delim == ",":
                        entry["Place"] = txt
                    elif delim == "—":
                        entry["Position"] = txt
                    elif delim == "|":
                        dates = re.split(r"\s*-\s*", txt)
                        entry["Date start"] = dates[0].strip()
                        entry["Date end"] = dates[1].strip() if len(dates) > 1 else dates[0].strip()
                entry["Data"] = []
                subsection_entries[name] = entry
                current_entry = entry
                last_bullet_idx = None

            else:
                if current_entry is None:
                    raise ValueError(f"Detail line without a header: {line}")
                if line.startswith("- "):
                    current_entry["Data"].append(line)
                    last_bullet_idx = len(current_entry["Data"]) - 1
                else:
                    if last_bullet_idx is None:
                        raise ValueError(f"Continuation without a bullet: {line}")
                    current_entry["Data"][last_bullet_idx] += " " + line

        sections[section_title] = subsection_entries

    return sections


class ResumeViewer(QMainWindow):
    """A PyQt5-based tree viewer for resume data with clipboard support."""
    def __init__(self, data: dict):
        super().__init__()
        self.setWindowTitle("Resume Viewer")
        self.showMaximized()

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Key", "Value"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)

        self._populate_tree(self.tree.invisibleRootItem(), data)
        self.tree.expandAll()
        self.tree.itemClicked.connect(self._handle_item_click)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.tree)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())

        quit_action = QAction(self)
        quit_action.setShortcut("Ctrl+W")
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    def _populate_tree(self, parent: QTreeWidgetItem, data):
        if isinstance(data, dict):
            for key, value in data.items():
                item = QTreeWidgetItem(parent, [key, ""])
                item.setData(0, Qt.UserRole, value)
                self._populate_tree(item, value)
        elif isinstance(data, list):
            parent.setData(0, Qt.UserRole, data)
            for elem in data:
                if isinstance(elem, (dict, list)):
                    child = QTreeWidgetItem(parent, ["", ""])
                    child.setData(0, Qt.UserRole, elem)
                    self._populate_tree(child, elem)
                else:
                    child = QTreeWidgetItem(parent, ["", str(elem)])
                    child.setData(0, Qt.UserRole, elem)
        else:
            parent.setText(1, str(data))
            parent.setData(0, Qt.UserRole, data)

    def _handle_item_click(self, item: QTreeWidgetItem, column: int):
        raw = item.data(0, Qt.UserRole)
        if isinstance(raw, list):
            text = "\n".join(str(x) for x in raw)
        elif isinstance(raw, dict):
            text = item.text(0)
        else:
            text = item.text(1) or item.text(0)
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("Copied to clipboard", 2000)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Resume PDF Viewer")
    parser.add_argument("pdf_path", nargs="?", default="Resume.pdf",
                        help="Path to the resume PDF file")
    args = parser.parse_args()

    try:
        data = parse_resume(args.pdf_path)
    except Exception as e:
        print(f"Error parsing {args.pdf_path}: {e}", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    try:
        with open("style.qss", "r") as qss_file:
            app.setStyleSheet(qss_file.read())
    except IOError:
        print("Warning: could not load style.qss", file=sys.stderr)
    
    viewer = ResumeViewer(data)
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
