# Resume Fetch & Deploy

A Node.js utility that automates the end-to-end process of fetching my resume from Google Docs, storing it locally in multiple directories, and deploying it to GitHub so my Next.js portfolio site always stays up to date.

## Features

* **Google Docs integration** via a GCP Service Account to securely download the latest PDF version of my resume.
* **Multi-directory storage** — automatically copies my resume into any set of local folders I specify (e.g., personal backups, shared drives).
* **GitHub auto-publish** — commits and pushes the updated resume PDF to my GitHub repository, triggering my Next.js site’s CI/CD pipeline.
* **One-step update** — run a single alias from anywhere in my shell:

  ```bash
  alias rupd='cd ~/Documents/Projects/fetch-resume/ && node index.js && cd -'
  ```

  Typing `rupd` will:

  1. Change into my project directory
  2. Execute the download & deployment script (`index.js`)
  3. Return me to my previous working directory

# Python Resume Viewer

For a quick GUI-based copy/paste of resume sections, I’ve included a PyQt5 desktop application:

## Features

* Loads and parses my PDF resume into a collapsible tree view
* Click any section, subsection, or bullet to copy its text to the clipboard
* Opens maximized with a colorized UI and supports **Ctrl+W** to close