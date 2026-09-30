import sys
import re
import os

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QStatusBar, QHeaderView, QAction
)
from PyQt5.QtCore import Qt


# ---------------------- LATEX PARSER ---------------------- #

def _strip_tex(text: str) -> str:
    """
    Strip simple LaTeX formatting commands, keeping readable text.
    """
    if text is None:
        return ""
    # Turn \textbf{foo} -> foo, same for \textit
    text = re.sub(r'\\textbf{([^}]*)}', r'\1', text)
    text = re.sub(r'\\textit{([^}]*)}', r'\1', text)
    # Replace explicit line breaks
    text = text.replace(r'\newline', ' ')
    # Common inline math symbols used in the resume
    text = text.replace(r'\times', '×')
    text = text.replace(r'\vert', '|')
    text = text.replace(r'\approx', '~')
    text = text.replace(r'\sim', '~')
    text = text.replace(r'\rightarrow', '->')
    # Unescape common escaped special characters (\& \% \$ \# \_)
    text = re.sub(r'\\([&%$#_])', r'\1', text)
    # Remove remaining simple commands like \hfill (but keep text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    # Remove extra braces
    text = text.replace('{', '').replace('}', '')
    # Remove leftover math-mode delimiters
    text = text.replace('$', '')
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _replace_hrefs(tex: str) -> str:
    """
    Replace \\href{url}{text} with the URL (or stripped mailto/tel value).
    """

    def repl(match):
        url = match.group(1)
        # display = match.group(2)  # not used; we keep URL instead
        if url.startswith("mailto:") or url.startswith("tel:"):
            return url.split(":", 1)[1]
        return url

    return re.sub(r'\\href{([^}]*)}{([^}]*)}', repl, tex)


def _parse_header(no_comments_tex: str) -> list:
    """
    Extract header info (name, LinkedIn, Email, Portfolio, Mobile) from the LaTeX.
    """
    header_lines = []

    # Header block: everything between \begin{document} and the first \section
    doc_match = re.search(
        r'\\begin{document}(.*?)\\section', no_comments_tex, re.DOTALL
    )
    header_block = doc_match.group(1) if doc_match else no_comments_tex

    # Name: either \textbf{{\Large Name}} or the older \textbf{\href{...}{\Large Name}}
    name_match = re.search(r'\\textbf{\\href{[^}]*}{\\Large ([^}]*)}}', header_block)
    if not name_match:
        name_match = re.search(r'\\textbf{{\\Large\s+([^}]*)}}', header_block)
    if name_match:
        header_lines.append(name_match.group(1).strip())

    # Contacts: bare \href{url}{display} pairs, classified by URL scheme/domain
    # rather than by label text, since the new template has no labels at all.
    contacts = {}
    order = []
    for url, display in re.findall(r'\\href{([^}]*)}{([^}]*)}', header_block):
        display = display.strip()
        if url.startswith("mailto:"):
            label = "Email"
        elif url.startswith("tel:"):
            label = "Mobile"
        elif "linkedin.com" in url.lower():
            label = "LinkedIn"
        else:
            label = "Portfolio"
        if label not in contacts:
            contacts[label] = display
            order.append(label)

    for label in ["LinkedIn", "Email", "Portfolio", "Mobile"]:
        if label in contacts:
            header_lines.append(f"{label}: {contacts[label]}")
    for label in order:
        if label not in ("LinkedIn", "Email", "Portfolio", "Mobile"):
            header_lines.append(f"{label}: {contacts[label]}")

    return header_lines


def _split_sections(tex: str) -> list:
    """
    Split the processed LaTeX into (section_name, section_body) tuples.
    """
    pattern = re.compile(r'\\section{([^}]*)}')
    matches = list(pattern.finditer(tex))
    sections = []

    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(tex)
        body = tex[start:end]
        sections.append((name, body))

    return sections


def _parse_education(body: str) -> dict:
    entries = {}

    pattern = re.compile(
        r'\\resumeEducationHeading\s*'
        r'{([^}]*)}\s*'   # Institution
        r'{([^}]*)}\s*'   # Dates
        r'{([^}]*)}',     # Degree / description
        re.DOTALL
    )

    for m in pattern.finditer(body):
        institution = _strip_tex(m.group(1))
        datestr = _strip_tex(m.group(2))
        degree = _strip_tex(m.group(3))

        dates = re.split(r'\s*[-–—]{1,2}\s*', datestr)
        start = dates[0].strip()
        end = dates[1].strip() if len(dates) > 1 else start

        entries[institution] = {
            "Degree": degree,
            "Date start": start,
            "Date end": end,
            "Data": []
        }

    return entries


def _extract_resume_items(block: str) -> list:
    """
    Extract bullet items from a block containing \resumeItem {...}.
    Handles one level of nested braces.
    """
    item_pattern = re.compile(
        r'\\resumeItem{((?:[^{}]|{[^{}]*})*)}',
        re.DOTALL
    )
    bullets = []
    for m in item_pattern.finditer(block):
        raw = m.group(1).strip()
        text = _strip_tex(raw)
        if text:
            bullets.append(f"- {text}")
    return bullets


def _parse_experience(body: str) -> dict:
    entries = {}

    heading_pattern = re.compile(
        r'\\resumeExperienceHeading\s*'
        r'{([^}]*)}\s*'   # Org
        r'{([^}]*)}\s*'   # Location
        r'{([^}]*)}\s*'   # Position
        r'{([^}]*)}',     # Dates
        re.DOTALL
    )

    itemlist_pattern = re.compile(
        r'\\resumeItemListStart(.+?)\\resumeItemListEnd',
        re.DOTALL
    )

    headings = list(heading_pattern.finditer(body))
    itemlists = list(itemlist_pattern.finditer(body))

    for h, il in zip(headings, itemlists):
        org = _strip_tex(h.group(1))
        location = _strip_tex(h.group(2))
        position = _strip_tex(h.group(3))
        datestr = _strip_tex(h.group(4))

        dates = re.split(r'\s*[-–—]{1,2}\s*', datestr)
        start = dates[0].strip()
        end = dates[1].strip() if len(dates) > 1 else start

        bullets = _extract_resume_items(il.group(1))

        entries[org] = {
            "Place": location,
            "Position": position,
            "Date start": start,
            "Date end": end,
            "Data": bullets
        }

    return entries


def _parse_projects(body: str) -> dict:
    entries = {}

    # Second arg is typically \href{url}{display}, i.e. one level of nested
    # braces, so a plain [^}]* group would stop at the href's inner brace.
    nested = r'((?:[^{}]|{[^{}]*})*)'
    pattern = re.compile(
        r'\\resumeProjectHeading\s*'
        r'{' + nested + r'}\s*'
        r'{' + nested + r'}'
        r'(.+?)\\resumeItemListEnd',
        re.DOTALL
    )

    for m in pattern.finditer(body):
        name = _strip_tex(m.group(1))
        url = _strip_tex(_replace_hrefs(m.group(2)))
        bullets = _extract_resume_items(m.group(3))

        entries[name] = {
            "URL": url,
            "Data": bullets
        }

    return entries


def _parse_research(body: str) -> dict:
    entries = {}

    pattern = re.compile(
        r'\\resumeResearchHeading\s*'
        r'{([^}]*)}'
        r'(.+?)\\resumeItemListEnd',
        re.DOTALL
    )

    for m in pattern.finditer(body):
        title = _strip_tex(m.group(1))
        bullets = _extract_resume_items(m.group(2))

        entries[title] = {
            "Data": bullets
        }

    return entries


def _parse_programming_skills(body: str) -> dict:
    """
    Parse the Skills section: a flat list of
    \\item\\small{\\textbf{Category}: value, value, ...} entries, one per
    category (categories are not fixed, e.g. "Languages", "Frameworks & Web").
    """
    skills = {}

    item_pattern = re.compile(
        r'\\item\\small{\\textbf{([^}]*)}\s*:\s*([^{}]*)}',
        re.DOTALL
    )
    for m in item_pattern.finditer(body):
        category = _strip_tex(m.group(1))
        values = [_strip_tex(v) for v in m.group(2).split(",")]
        values = [v for v in values if v]
        if category:
            skills[category] = values

    return skills


def parse_resume(tex_path: str) -> dict:
    """
    Parse the LaTeX resume (sb2nov-style template) into a nested dict structure.
    """
    with open(tex_path, "r", encoding="utf-8") as f:
        original_tex = f.read()

    # Drop comment lines
    no_comments = "\n".join(
        line for line in original_tex.splitlines()
        if not line.strip().startswith("%")
    )

    # Replace hrefs with URLs / emails / phones
    processed = _replace_hrefs(no_comments)

    sections = {}

    # Header
    header_lines = _parse_header(no_comments)
    sections["Header"] = header_lines

    # Split into \section{...}
    for raw_name, body in _split_sections(processed):
        # Section names can contain escaped chars, e.g. "Leadership \& Involvement"
        name = _strip_tex(raw_name)

        if name == "Education":
            sections[name] = _parse_education(body)
        elif name == "Experience":
            sections[name] = _parse_experience(body)
        elif name == "Projects":
            sections[name] = _parse_projects(body)
        elif name == "Research":
            sections[name] = _parse_research(body)
        elif name in ("Programming Skills", "Skills"):
            sections[name] = _parse_programming_skills(body)
        # Fallback for sections under other names (e.g. "Leadership &
        # Involvement") that reuse one of the known heading macros.
        elif r'\resumeExperienceHeading' in body:
            sections[name] = _parse_experience(body)
        elif r'\resumeProjectHeading' in body:
            sections[name] = _parse_projects(body)
        elif r'\resumeEducationHeading' in body:
            sections[name] = _parse_education(body)
        elif r'\resumeResearchHeading' in body:
            sections[name] = _parse_research(body)
        else:
            # Fallback: store raw body (stripped)
            sections[name] = _strip_tex(body)

    return sections


# ---------------------- QT VIEWER ---------------------- #

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
    parser = argparse.ArgumentParser(description="Resume LaTeX Viewer")
    parser.add_argument("path", nargs="?", default="/home/hackoverflow404/Documents/Projects/Resume/Resume.tex",
                        help="Path to the resume LaTeX (.tex) file")
    args = parser.parse_args()

    try:
        data = parse_resume(args.path)
    except Exception as e:
        print(f"Error parsing {args.path}: {e}", file=sys.stderr)
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