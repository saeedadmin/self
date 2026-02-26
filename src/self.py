import asyncio
import os
import sys
import time

import aiohttp
from aiohttp import web
import scren_tools
from dotenv import load_dotenv
from mistralai import Mistral
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, MessageDeleteForbiddenError
from telethon.tl.functions.messages import DeleteMessagesRequest


load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PRICE_KEY = os.getenv("PRICE_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

client = TelegramClient("iQ self", API_ID, API_HASH, device_model="IPhone 13 Pro")

# Utilities
async def fetch_json(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                return await response.json()
    except Exception:
        return None

async def fetch_price(price_type):
    url = f"http://xprimarytool.f5f102.site/price?key={PRICE_KEY}&price={price_type}"
    data = await fetch_json(url)
    return data["price"] if data and "price" in data else "Error"

# 🔥 Ai
async def ask_ai(prompt: str) -> str:
    """Ask the AI for a response to a prompt.

    :param prompt: The prompt to send to the AI
    :return: The AI's response or an error message if something went wrong
    """
    if not prompt:
        return "❌ Prompt is empty."

    try:
        def sync_call():
            with Mistral(api_key=MISTRAL_API_KEY) as mistral:
                return mistral.chat.complete(
                    model="mistral-large-latest",
                    messages=[
                        {
                            "role": "user",
                            "content": f"Answer this question in one paragraph : {prompt}",
                        }
                    ],
                    stream=False,
                )
            
        res = await asyncio.to_thread(sync_call)

        # text answer
        return res.choices[0].message.content.strip()

    except Exception as e:
        return f"❌ AI Error: {str(e)}"

# Handelers
@client.on(events.NewMessage(pattern=r"(?i)^\.self$", outgoing=True))
async def self_handler(event):
    await event.edit("**iQ Self is always on...**")

@client.on(events.NewMessage(pattern=r"(?i)^\.restart$", outgoing=True))
async def restart_handler(event):
    await event.edit("**Restarting...**")
    python = sys.executable
    os.execl(python, python, *sys.argv)

@client.on(events.NewMessage(pattern=r"(?i)^\.ping$", outgoing=True))
async def ping_handler(event):
    start = time.time()
    await event.edit("**Pinging...**")
    ping = (time.time() - start) * 1000
    await event.edit(f"**Ping:** `{ping:.0f} ms`")

@client.on(events.NewMessage(pattern=r"(?i)^\.price$", outgoing=True))
async def price_handler(event):
    await event.edit("**Fetching prices...**")

    usd, euro, gold18, gold24 = await asyncio.gather(
        fetch_price("usd"),
        fetch_price("euro"),
        fetch_price("gold18"),
        fetch_price("gold24"),
    )

    text = (
        "**Global Currency Prices**\n\n"
        f"USD » {usd}\n"
        f"Euro » {euro}\n"
        f"Gold 18K » {gold18}\n"
        f"Gold 24K » {gold24}\n\n"
        "**iQ Self**"
    )

    await event.edit(text)

@client.on(events.NewMessage(pattern=r"(?i)^\.screen (.+)$", outgoing=True))
async def screen_handler(event):
    url = event.pattern_match.group(1)
    await event.edit("**Taking screenshot...**")

    try:
        scren_tools.screen(url)
        await event.delete()
        await client.send_file(
            event.chat_id, "screen.png", caption="**iQ Self is always ready to serve**"
        )
    except Exception:
        await event.edit("**Screenshot failed.**")

@client.on(events.NewMessage(pattern=r"(?i)^\.tools$", outgoing=True))
async def tools_handler(event):
    await event.edit(
        "**Tools**\n\n"
        "`.price` » Currency prices\n"
        "`.screen <url>` » Website screenshot"
    )

@client.on(events.NewMessage(pattern=r"(?i)^\.status$", outgoing=True))
async def status_handler(event):
    session_size = os.path.getsize("iQ self.session")
    session_size_mb = session_size / (1024 * 1024)
    await event.edit(f"**Session size:** {session_size_mb:.2f} MB")

@client.on(events.NewMessage(pattern=r"(?i)^\.ai(?:\s+(.*))?$", outgoing=True))
async def ai_check(event):
    question = event.pattern_match.group(1)

    text = None

    if event.is_reply and question:
        replied = await event.get_reply_message()
        replied_text = replied.text or replied.caption

        if not replied_text:
            await event.edit("**No text or caption found in replied message**")
            return

        text = f"{replied_text}\n\nUser question: {question.strip()}"

    elif event.is_reply:
        replied = await event.get_reply_message()
        text = replied.text or replied.caption

        if not text:
            await event.edit("**No text or caption found in replied message**")
            return

    elif question:
        text = question.strip()

    else:
        await event.edit("**Reply to a message or write a question after .ai**")
        return
    
    if question:
        await event.edit(f"{question} \n Processing...")
    else:
        await event.edit("**Processing...**")
    response = await ask_ai(text)

    await event.edit(
    f"**Question:**\n{question.strip()}\n\n**Answer:**\n{response}"
    if question and question.strip()
    else f"**Answer:**\n{response}"
    )

MAX_DELETE = 1000
CHUNK_SIZE = 100
@client.on(events.NewMessage(pattern=r"(?i)^\.purge(?:\s+(\d+))?$", outgoing=True))
async def purge_handler(event):
    start_time = time.time()
    count = event.pattern_match.group(1)

    if not count and not event.is_reply:
        await event.edit("Reply or provide number of messages to delete.")
        return

    count = int(count) if count else 0

    if count > MAX_DELETE:
        await event.edit(f"Limit is {MAX_DELETE} messages max.")
        return

    messages_to_delete = []
    deleted = 0
    errors = 0
    flood_wait_time = 0

    try:
        # حالت ریپلای
        if event.is_reply:
            reply = await event.get_reply_message()
            async for msg in client.iter_messages(
                event.chat_id,
                min_id=reply.id
            ):
                messages_to_delete.append(msg.id)
                if count and len(messages_to_delete) >= count:
                    break

        # حالت عدد بدون ریپلای (فقط پیام‌های خودت)
        else:
            async for msg in client.iter_messages(
                event.chat_id,
                limit=count + 1,
                max_id=event.id
            ):
                if msg.id != event.id:
                    messages_to_delete.append(msg.id)

                if len(messages_to_delete) >= count:
                    break

        await event.delete()

        # حذف دسته‌ای
        for i in range(0, len(messages_to_delete), CHUNK_SIZE):
            chunk = messages_to_delete[i:i + CHUNK_SIZE]

            while True:
                try:
                    result = await client.delete_messages(
                        event.chat_id,
                        chunk
                    )

                    if result:
                        deleted += len(chunk)
                    else:
                        errors += len(chunk)

                    break

                except FloodWaitError as e:
                    flood_wait_time += e.seconds
                    await asyncio.sleep(e.seconds)

                except Exception:
                    errors += len(chunk)
                    break

        duration = round(time.time() - start_time, 2)

        report = (
            f"🧹 Purge Completed\n\n"
            f"Deleted: {deleted}\n"
            f"Errors: {errors}\n"
            f"FloodWait: {flood_wait_time}s\n"
            f"Time: {duration}s"
        )

        await client.send_message(event.chat_id, report)

    except Exception as e:
        await client.send_message(
            event.chat_id,
            f"❌ Unexpected error:\n{str(e)}"
        )
# Start
async def main():
    await client.start()
    await client.send_message("me", "**iQ Self run**\n`.panel`")
    await client.run_until_disconnected()

asyncio.run(main())

async def handle(request):
    return web.Response(text="iQ Self running!")

app = web.Application()
app.router.add_get("/", handle)

web.run_app(app, port=8000)
