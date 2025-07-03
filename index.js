import { finished } from "stream/promises";
import { execSync } from "child_process";
import { createWriteStream } from "fs";
import { join, resolve } from "path";
import { google } from "googleapis";
import "dotenv/config";

async function downloadResume() {
  const docId = process.env["DOC_ID"];
  if (!docId) {
    console.error("DOC_ID environment variable not set.");
    process.exit(1);
  }

  const auth = new google.auth.GoogleAuth({
    keyFile: resolve("credentials.json"),
    scopes: ["https://www.googleapis.com/auth/drive.readonly"],
  });

  const drive = google.drive({ version: "v3", auth });

  const destPaths = [
    resolve("../../job_docs/Resume.pdf"),
    resolve("../portfolio/public/Resume.pdf"),
    resolve("./Resume.pdf"),
  ];

  const res = await drive.files.export(
    {
      fileId: docId,
      mimeType: "application/pdf",
    },
    { responseType: "stream" }
  );

  await Promise.all(
    destPaths.map(async (destPath) => {
      const dest = createWriteStream(destPath);
      res.data.pipe(dest);
      await finished(dest);
      console.log(`Written to ${destPath}`);
    })
  );

  try {
    execSync("cd ~/Documents/Projects/portfolio && npm run build && git add ./public/Resume.pdf && git commit -m 'Chore: Update Resume' && git push", {
      stdio: "inherit",
    });
    console.log("Pushed updated resume to portfolio repository.");
  } catch (err) {
    console.error("Git commit/push failed:", err);
  }
}

downloadResume().catch((err) => {
  console.error("Resume download failed:", err);
});