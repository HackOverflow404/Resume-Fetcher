import { execSync } from "child_process";
import { copyFileSync, existsSync, mkdirSync } from "fs";
import { dirname, join, resolve } from "path";

const RESUME_REPO = "/home/hackoverflow404/Documents/Projects/Resume";
const VARIANTS = ["swe", "security", "infra"];
const PDF_NAME = "Medhansh_Garg_Resume.pdf";

// Every variant is copied to <dir>/resumes/<variant>/Medhansh_Garg_Resume.pdf
const VARIANT_DEST_DIRS = [
  "/home/hackoverflow404/Documents/job_docs",
  "/mnt/mainframe-shodan/job_docs",
  resolve("."),
];

// The portfolio serves every variant at public/resumes/<variant>/, plus the SWE
// resume at public/ root so older links to it keep working
const PORTFOLIO_ROOT_VARIANT = "swe";

function run(cmd, cwd) {
  console.log(`\n$ (cwd=${cwd ?? process.cwd()}) ${cmd}`);
  execSync(cmd, { stdio: "inherit", cwd });
}

function copy(sourcePath, destPath) {
  mkdirSync(dirname(destPath), { recursive: true });
  copyFileSync(sourcePath, destPath);
  console.log(`Copied resume to: ${destPath}`);
}

async function updateResume() {
  // 0) Rebuild all variants so the PDFs match the .tex sources
  run("make", RESUME_REPO);

  const sourcePath = (variant) => join(RESUME_REPO, variant, PDF_NAME);

  for (const variant of VARIANTS) {
    if (!existsSync(sourcePath(variant))) {
      console.error("Resume source file not found:", sourcePath(variant));
      process.exit(1);
    }
  }

  for (const variant of VARIANTS) {
    for (const destDir of VARIANT_DEST_DIRS) {
      copy(sourcePath(variant), join(destDir, "resumes", variant, PDF_NAME));
    }
  }

  const portfolioDir = "/home/hackoverflow404/Documents/Projects/portfolio";
  for (const variant of VARIANTS) {
    copy(sourcePath(variant), join(portfolioDir, "public", "resumes", variant, PDF_NAME));
  }
  copy(sourcePath(PORTFOLIO_ROOT_VARIANT), join(portfolioDir, "public", PDF_NAME));

  try {
    // 1) Build (this is where your `window is not defined` happens)
    run("npm run build", portfolioDir);

    // 2) Stage file
    run(`git add public/${PDF_NAME} public/resumes`, portfolioDir);

    // 3) Commit, but tolerate "nothing to commit"
    try {
      run(`git commit -m "Chore: Update Resume"`, portfolioDir);
    } catch (e) {
      // If commit failed because there was nothing to commit, just skip push
      console.log("No changes to commit (git commit failed). Skipping push.");
      return;
    }

    // 4) Push
    run("git push", portfolioDir);

    console.log("Portfolio updated and resume pushed successfully.");
  } catch (err) {
    console.error("Git/build step failed:", err);
  }
}

updateResume().catch((err) => {
  console.error("Resume update failed:", err);
});
