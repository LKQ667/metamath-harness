#!/usr/bin/env node
/**
 * 独立识图脚本 — 调用阿里云百炼多模态模型（OpenAI 兼容接口），按量付费。
 *
 * 用法:
 *   node vision.js <图片路径> [问题]
 *   node vision.js --url <图片链接> [问题]
 *
 * 配置:
 *   仅读取调用进程显式提供的环境变量；绝不自动读取任何 .env 文件。
 *   DASHSCOPE_API_KEY  必填，百炼 API Key
 *   VISION_MODELS      可选，逗号分隔的模型列表，按顺序尝试，失败自动切换下一个
 *   DASHSCOPE_BASE_URL 可选，OpenAI 兼容接口地址（默认百炼 compatible-mode）
 */

const fs = require("fs");
const path = require("path");
const https = require("https");
const http = require("http");

const BASE_URL =
  process.env.DASHSCOPE_BASE_URL || "https://dashscope.aliyuncs.com/compatible-mode/v1";
const API_KEY = process.env.DASHSCOPE_API_KEY || "";
const MODELS = (
  process.env.VISION_MODELS ||
  process.env.VISION_MODEL ||
  "qwen3.7-plus,qwen3.7-flash-2026-07-15"
)
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

function parseArgs() {
  const argv = process.argv.slice(2);
  let imageSource = "", prompt = "", isUrl = false;

  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--url" && argv[i + 1]) {
      isUrl = true;
      imageSource = argv[++i];
    } else if (!imageSource && !argv[i].startsWith("--")) {
      imageSource = argv[i];
    } else if (imageSource && !argv[i].startsWith("--")) {
      prompt = prompt ? prompt + " " + argv[i] : argv[i];
    }
  }
  if (!prompt) prompt = "请详细描述这张图片的内容。";
  return { imageSource, prompt, isUrl };
}

function resolveImageUrl(source, isUrl) {
  if (isUrl) return source;
  const resolved = path.resolve(source);
  if (!fs.existsSync(resolved)) throw new Error(`文件不存在: ${resolved}`);
  const ext = path.extname(resolved).toLowerCase().replace(".", "");
  const mimeMap = { jpg: "jpeg", jpeg: "jpeg", png: "png", gif: "gif", webp: "webp", bmp: "bmp" };
  const data = fs.readFileSync(resolved);
  return `data:image/${mimeMap[ext] || "jpeg"};base64,${data.toString("base64")}`;
}

function request(payload) {
  const url = new URL(BASE_URL.replace(/\/?$/, "/") + "chat/completions");
  const body = JSON.stringify(payload);
  const transport = url.protocol === "https:" ? https : http;

  return new Promise((resolve, reject) => {
    const req = transport.request(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(body),
      },
    }, (res) => {
      let data = "";
      res.on("data", (c) => data += c);
      res.on("end", () => {
        if (res.statusCode >= 400) return reject(new Error(`API ${res.statusCode}: ${data.slice(0, 300)}`));
        try {
          resolve(JSON.parse(data)?.choices?.[0]?.message?.content || data);
        } catch { resolve(data); }
      });
    });
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function main() {
  if (!API_KEY || API_KEY === "sk-xxx") {
    console.error("未配置 DASHSCOPE_API_KEY：独立脚本只接受调用进程显式设置的环境变量。");
    console.error("获取 Key: https://bailian.console.aliyun.com/");
    process.exit(1);
  }
  const { imageSource, prompt, isUrl } = parseArgs();
  if (!imageSource) {
    console.error("用法: node vision.js <图片路径> [问题]");
    console.error("      node vision.js --url <图片链接> [问题]");
    process.exit(1);
  }

  let imageUrl;
  try {
    imageUrl = resolveImageUrl(imageSource, isUrl);
  } catch (err) {
    console.error("识图失败:", err.message);
    process.exit(1);
  }

  let lastError = null;
  for (const model of MODELS) {
    try {
      const result = await request({
        model,
        messages: [{ role: "user", content: [
          { type: "image_url", image_url: { url: imageUrl } },
          { type: "text", text: prompt },
        ]}],
        stream: false,
        max_tokens: 1024,
      });
      console.log(result);
      return;
    } catch (err) {
      lastError = err;
      console.error(`模型 ${model} 识图失败: ${err.message}`);
    }
  }
  console.error(`所有模型均失败（共 ${MODELS.length} 个）:`, lastError ? lastError.message : "未知错误");
  process.exit(1);
}

main();
