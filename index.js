import { execSync } from "child_process";
import { copyFileSync, existsSync } from "fs";
import { resolve } from "path";

function run(cmd, cwd) {
  console.log(`\n$ (cwd=${cwd ?? process.cwd()}) ${cmd}`);
  execSync(cmd, { stdio: "inherit", cwd });
}

async function updateResume() {
  const sourcePath = "/home/hackoverflow/Documents/Projects/Resume/Resume.pdf";

  const destPaths = [
    "/home/hackoverflow/Documents/job_docs/Resume.pdf",
    "/home/hackoverflow/Documents/Projects/portfolio/public/Resume.pdf",
    resolve("./Resume.pdf"),
  ];

  if (!existsSync(sourcePath)) {
    console.error("Resume source file not found:", sourcePath);
    process.exit(1);
  }

  for (const destPath of destPaths) {
    copyFileSync(sourcePath, destPath);
    console.log(`Copied resume to: ${destPath}`);
  }

  const portfolioDir = "/home/hackoverflow/Documents/Projects/portfolio";

  try {
    // 1) Build (this is where your `window is not defined` happens)
    run("npm run build", portfolioDir);

    // 2) Stage file
    run("git add public/Resume.pdf", portfolioDir);

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
