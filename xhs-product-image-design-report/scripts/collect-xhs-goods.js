const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = { urlsFile: "", outDir: "" };
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--urls-file") parsed.urlsFile = args[++i];
    else if (args[i] === "--out-dir") parsed.outDir = args[++i];
  }
  if (!parsed.urlsFile || !parsed.outDir) {
    console.error("Usage: node collect-xhs-goods.js --urls-file 商品链接.txt --out-dir 输出结果");
    process.exit(2);
  }
  return parsed;
}

function readUrls(filePath) {
  return fs
    .readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
}

async function extractOne(page, url, index, outDir) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForTimeout(5000);

  const screenshotPath = path.join(outDir, `商品${index}_页面截图.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  const data = await page.evaluate(() => {
    const images = Array.from(document.images)
      .map((img) => ({
        src: img.currentSrc || img.src,
        alt: img.alt || "",
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        width: Math.round(img.getBoundingClientRect().width),
        height: Math.round(img.getBoundingClientRect().height),
      }))
      .filter((img) => img.src);

    const backgroundImages = [];
    document.querySelectorAll("*").forEach((el) => {
      const bg = getComputedStyle(el).backgroundImage;
      const match = bg && bg.match(/url\(["']?(.*?)["']?\)/);
      if (match) backgroundImages.push(match[1]);
    });

    return {
      url: location.href,
      title: document.title,
      text: document.body.innerText,
      images,
      backgroundImages: Array.from(new Set(backgroundImages)),
    };
  });

  return { index, inputUrl: url, screenshotPath, ...data };
}

(async () => {
  const { urlsFile, outDir } = parseArgs();
  fs.mkdirSync(outDir, { recursive: true });
  const urls = readUrls(urlsFile);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 1200 } });
  const results = [];

  for (let i = 0; i < urls.length; i += 1) {
    try {
      results.push(await extractOne(page, urls[i], i + 1, outDir));
    } catch (error) {
      results.push({
        index: i + 1,
        inputUrl: urls[i],
        error: String(error && error.stack ? error.stack : error),
      });
    }
  }

  await browser.close();

  fs.writeFileSync(
    path.join(outDir, "公开字段抽取.json"),
    JSON.stringify(results, null, 2),
    "utf8",
  );

  console.log(
    JSON.stringify(
      results.map((item) => ({
        index: item.index,
        inputUrl: item.inputUrl,
        title: item.title || "",
        imageCount: item.images ? item.images.length : 0,
        backgroundImageCount: item.backgroundImages ? item.backgroundImages.length : 0,
        error: item.error || "",
      })),
      null,
      2,
    ),
  );
})();
