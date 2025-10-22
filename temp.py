import logging
import json
import requests
import hashlib
import random
import uuid
import asyncio
import os
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# Enable logging for detailed output
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher level for httpx to avoid verbose logs
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Use environment variables with fallback values for local development
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8031723513:AAGM8euqDu9dUVihc3eTmCFCctnMIOi-RkE")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "87071f5058msh58c5d676b796932p18d2f2jsnc18747d0890c")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "privatix-temp-mail-v1.p.rapidapi.com")

# Dictionary to store the temporary email for each user.
# The key is the user's chat ID, and the value is their email address.
user_emails = {}

# Dictionary to store message IDs for a user's current session.
# This helps the bot remember which emails were fetched so the user can read them.
# The key is the user's chat ID, and the value is a dictionary mapping a message ID to its subject.
user_message_ids = {}

# --- HELPER FUNCTIONS ---

def get_email_hash(email: str) -> str:
    """Generates the MD5 hash of an email address."""
    return hashlib.md5(email.encode('utf-8')).hexdigest()

# --- TELEGRAM BOT COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and instructions to the user."""
    await update.message.reply_text(
        "👋 Welcome! I'm a temporary email bot. "
        "Here's what I can do:\n\n"
        "/new - Generate a new temporary email address.\n"
        "/check - Check your inbox for new messages.\n"
        "/read <message_id> - Read a specific message.\n"
        "/delete - Delete your current temporary email."
    )

async def new_email_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a new temporary email address for the user."""
    chat_id = update.effective_chat.id
    
    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }
    
    # Get the list of available domains
    try:
        response = requests.get(f"https://{RAPIDAPI_HOST}/request/domains/", headers=headers)
        response.raise_for_status()
        domains = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching domains: {e}")
        await update.message.reply_text("Sorry, I couldn't get a list of domains right now. Please try again later.")
        return

    if not domains:
        await update.message.reply_text("Sorry, no domains are available. Please try again later.")
        return

    # Generate a random username and choose a random domain
    username = str(uuid.uuid4().hex[:10])
    domain = random.choice(domains)
    new_email = f"{username}{domain}"

    # Store the new email for the user
    user_emails[chat_id] = new_email
    
    await update.message.reply_text(
        f"✅ Your new temporary email address is:\n`{new_email}`\n\n"
        "You can now receive emails. Use /check to see new messages."
    )

async def check_inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks the inbox for the user's current temporary email."""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_emails:
        await update.message.reply_text("You need to generate an email first. Use /new.")
        return
        
    email_address = user_emails[chat_id]
    email_hash = get_email_hash(email_address)

    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }

    emails = []
    try:
        response = requests.get(f"https://{RAPIDAPI_HOST}/request/mail/id/{email_hash}/", headers=headers)
        response.raise_for_status()
        
        # Check if the response content is a list before parsing as JSON.
        # Handle cases where the API returns an error message instead of a list.
        if response.content:
            data = response.json()
            if isinstance(data, list):
                emails = data
            elif isinstance(data, dict) and 'error' in data:
                # The API returns an error object like {"error":"There are no emails yet"}
                logger.info(f"API returned an error, assuming no new emails: {data['error']}")
                emails = [] # Treat this as an empty inbox
            else:
                logger.error(f"Unexpected response format from API: {response.text}")
                await update.message.reply_text("Sorry, there was an unexpected issue checking your inbox. Please try again later.")
                return
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking inbox for {email_address}: {e}")
        await update.message.reply_text("Sorry, I couldn't check your inbox right now. Please try again later.")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response: {e}")
        await update.message.reply_text("Sorry, there was an error processing the response from the API. Please try again later.")
        return

    if not emails:
        await update.message.reply_text("📥 Your inbox is empty.")
    else:
        inbox_message = "📬 **Your Inbox**:\n\n"
        user_message_ids[chat_id] = {} # Clear previous message IDs
        for email in emails:
            # CORRECTED: Use the 'mail_id' field for the message ID.
            # This is the correct ID to use for the '/read' endpoint.
            message_id = email.get('mail_id')
            subject = email.get('mail_subject', 'No Subject')
            from_address = email.get('mail_from', 'Unknown Sender')
            
            # Check if message_id is valid before storing
            if not message_id:
                logger.warning(f"Message in response is missing a valid mail_id: {email}")
                continue

            user_message_ids[chat_id][message_id] = subject
            
            # Show a summary of each email
            inbox_message += (
                f"**ID:** `{message_id}`\n"
                f"**From:** `{from_address}`\n"
                f"**Subject:** `{subject}`\n"
                f"--------------------\n"
            )
        
        await update.message.reply_text(inbox_message, parse_mode='Markdown')
        await update.message.reply_text("Use `/read <message_id>` to view the full content of an email.")

async def read_email_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reads the content of a specific email by its message ID."""
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Please provide a message ID. E.g., `/read <message_id>`.")
        return
    
    message_id = context.args[0]
    
    if chat_id not in user_message_ids or message_id not in user_message_ids[chat_id]:
        await update.message.reply_text("That message ID is not valid or has expired. Please use /check to get a new list of messages.")
        return

    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }

    try:
        # The API endpoint for reading a specific message by its ID
        response = requests.get(f"https://{RAPIDAPI_HOST}/request/id/{message_id}/", headers=headers)
        response.raise_for_status()
        email_content = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error reading message {message_id}: {e}")
        await update.message.reply_text("Sorry, I couldn't retrieve that message. It may have been deleted.")
        return
    
    # Extract relevant fields
    subject = email_content.get('mail_subject', 'No Subject')
    from_address = email_content.get('mail_from', 'Unknown Sender')
    date = email_content.get('createdAt', {}).get('milliseconds')
    content = email_content.get('mail_text_only', 'No content.')

    full_message = (
        f"**From:** `{from_address}`\n"
        f"**Subject:** `{subject}`\n"
        f"**Date:** `{date}`\n\n"
        f"--- Message Content ---\n"
        f"```\n{content}\n```"
    )

    await update.message.reply_text(full_message, parse_mode='Markdown')

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes the user's current temporary email address."""
    chat_id = update.effective_chat.id

    if chat_id not in user_emails:
        await update.message.reply_text("You don't have an active email to delete.")
        return
    
    email_address = user_emails[chat_id]
    email_hash = get_email_hash(email_address)

    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST
    }

    try:
        # The API endpoint for deleting an email by its ID is:
        # `https://privatix-temp-mail-v1.p.rapidapi.com/request/delete/id/{mail_id}/`
        response = requests.get(f"https://{RAPIDAPI_HOST}/request/delete/id/{email_hash}/", headers=headers)
        response.raise_for_status()
        await update.message.reply_text(f"🗑️ The temporary email address `{email_address}` has been deleted.")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting email {email_address}: {e}")
        await update.message.reply_text("There was an error trying to delete your email. It may have already expired.")
    finally:
        # Clear the email from our local storage regardless of API success
        if chat_id in user_emails:
            del user_emails[chat_id]
        if chat_id in user_message_ids:
            del user_message_ids[chat_id]

def main() -> None:
    """Start the bot."""
    # Validate that required environment variables are set
    if not BOT_TOKEN or BOT_TOKEN == "8031723513:AAGM8euqDu9dUVihc3eTmCFCctnMIOi-RkE":
        logger.warning("Using default BOT_TOKEN. For production, set the BOT_TOKEN environment variable.")
    
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "87071f5058msh58c5d676b796932p18d2f2jsnc18747d0890c":
        logger.warning("Using default RAPIDAPI_KEY. For production, set the RAPIDAPI_KEY environment variable.")
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("new", new_email_command))
    application.add_handler(CommandHandler("check", check_inbox_command))
    application.add_handler(CommandHandler("read", read_email_command))
    application.add_handler(CommandHandler("delete", delete_command))
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
