export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(200).send("TradeAgent-HK Telegram bot is running.");
  }

  const {
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_WEBHOOK_SECRET,
    GH_PAT,
    GITHUB_OWNER = "nunufung",
    GITHUB_REPO = "TradeAgent-HK",
    GITHUB_WORKFLOW = "hk-daily.yml",
  } = process.env;

  // Verify request really came from Telegram
  const secret = req.headers["x-telegram-bot-api-secret-token"];

  if (secret !== TELEGRAM_WEBHOOK_SECRET) {
    return res.status(403).json({ ok: false });
  }

  const message = req.body?.message;

  if (!message?.text) {
    return res.status(200).json({ ok: true });
  }

  const chatId = String(message.chat.id);

  // Only allow your Telegram account/chat to trigger analysis
  if (chatId !== String(TELEGRAM_CHAT_ID)) {
    return res.status(200).json({ ok: true });
  }

  const input = message.text.trim();

  // User only needs to type 1-4 digits, e.g. 5, 700, 981, 9988
  if (!/^\d{1,4}$/.test(input)) {
    await sendTelegram(
      TELEGRAM_BOT_TOKEN,
      TELEGRAM_CHAT_ID,
      "Please enter only a Hong Kong stock code, for example:\n700\n981\n9988\n2800"
    );

    return res.status(200).json({ ok: true });
  }

  const ticker = String(parseInt(input, 10));

  await sendTelegram(
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    `🔎 TradeAgent-HK\n\nAnalyzing ${ticker.padStart(4, "0")}.HK...\n\nYour PDF report will be sent when analysis is complete.`
  );

  const githubResponse = await fetch(
    `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${GITHUB_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${GH_PAT}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: {
          ticker: ticker,
        },
      }),
    }
  );

  if (!githubResponse.ok) {
    const error = await githubResponse.text();

    console.error("GitHub dispatch failed:", error);

    await sendTelegram(
      TELEGRAM_BOT_TOKEN,
      TELEGRAM_CHAT_ID,
      "⚠️ I could not start the analysis. Please check the GitHub/Vercel configuration."
    );

    return res.status(200).json({ ok: false });
  }

  return res.status(200).json({ ok: true });
}

async function sendTelegram(token, chatId, text) {
  const response = await fetch(
    `https://api.telegram.org/bot${token}/sendMessage`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        chat_id: chatId,
        text: text,
      }),
    }
  );

  if (!response.ok) {
    console.error("Telegram send failed:", await response.text());
  }
}
