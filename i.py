# telegram_bot.py

import logging
import asyncio
from pymailtm import MailTm
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- Configuration ---
# Replace this with your bot token provided by BotFather.
BOT_TOKEN = "8444165710:AAGdrrL7rxdBudCf1amuFldtcYQ1KSFySIE"

# Replace this with your own Telegram user ID. You can get it from a bot like @userinfobot.
# This ID will be used to grant access to the admin panel.
ADMIN_ID = 6994528708  # TODO: Change this to your actual user ID

# Enable logging for a better understanding of the bot's behavior
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# A simple in-memory dictionary to store user data.
# In a real-world application, this should be replaced with a persistent database
# like Firestore to avoid data loss when the bot restarts.
# The structure will be: {telegram_user_id: MailTm.Account}
user_accounts = {}

# --- Bot Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message with a list of commands when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hello, {user.mention_html()}! 👋\n"
        "I can provide you with a temporary email address. Use the commands below:\n"
        "• /new_email - Get a new disposable email address.\n"
        "• /check_inbox - Check your inbox for new emails.\n"
        "• /my_email - See your current email address.\n"
        "• /help - See all available commands.\n\n"
        "<b>Warning:</b> This service is for temporary use only. Do not use it for sensitive data."
    )

async def my_email_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the user's current email address or prompts them to create one."""
    user_id = update.effective_user.id
    if user_id in user_accounts:
        await update.message.reply_html(
            f"Your current temporary email address is:\n"
            f"<code>{user_accounts[user_id].address}</code>"
        )
    else:
        await update.message.reply_text(
            "You don't have an email address yet. Please use the /new_email command to create one."
        )

async def new_email_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a new temporary email address for the user."""
    user_id = update.effective_user.id
    if user_id in user_accounts:
        await update.message.reply_text(
            "You already have an email address. If you need a new one, you must delete the current one first."
        )
        return

    await update.message.reply_text("Generating a new temporary email address...")

    try:
        # Create a new account using the pymailtm library.
        mt = MailTm()
        account = mt.get_account()
        user_accounts[user_id] = account
        
        await update.message.reply_html(
            "Your new temporary email address is:\n"
            f"<code>{account.address}</code>\n"
            "This address has been saved for you. Use /check_inbox to see new messages."
        )
    except Exception as e:
        logging.error(f"Error creating account for user {user_id}: {e}")
        await update.message.reply_text(
            "Failed to create a new email address. Please try again later."
        )

async def check_inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks the user's temporary email inbox for new messages."""
    user_id = update.effective_user.id
    if user_id not in user_accounts:
        await update.message.reply_text(
            "You don't have an email address yet. Use /new_email to get one."
        )
        return
    
    account = user_accounts[user_id]
    await update.message.reply_text("Checking your inbox for new messages...")
    
    try:
        # Retrieve messages from the account using the pymailtm library.
        messages = account.get_messages()
        
        if not messages:
            await update.message.reply_text("Your inbox is empty.")
        else:
            response_text = "<b>New messages in your inbox:</b>\n\n"
            for message in messages:
                response_text += (
                    f"<b>From:</b> {message.from_['address']}\n"
                    f"<b>Subject:</b> {message.subject}\n"
                    f"<b>Intro:</b> {message.intro}\n"
                    f"<b>Body:</b> {message.text}\n"
                    f"----------------------------------------\n"
                )
            await update.message.reply_html(response_text)
    except Exception as e:
        logging.error(f"Error checking inbox for user {user_id}: {e}")
        await update.message.reply_text(
            "An error occurred while checking your inbox. Your account may have expired."
        )
        # Remove the expired account from the dictionary
        del user_accounts[user_id]

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the admin panel commands if the user is an admin."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    admin_commands = (
        "<b>Admin Panel</b>\n\n"
        "Welcome, Admin! Here are your available commands and features:\n"
        "• /broadcast [message] - Send a message to all active users.\n"
        "• /delete_account [user_id] - Delete a user's temporary account.\n"
        "• /get_all_users - List all active users and their email addresses.\n"
        "• /stats - See bot usage statistics."
    )
    await update.message.reply_html(admin_commands)

async def get_all_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to list all active users and their emails."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not user_accounts:
        await update.message.reply_text("No users have created temporary accounts yet.")
        return

    response_text = "<b>Active Users:</b>\n\n"
    for telegram_id, account in user_accounts.items():
        response_text += f"<b>User ID:</b> <code>{telegram_id}</code>\n"
        response_text += f"<b>Email:</b> <code>{account.address}</code>\n"
        response_text += f"----------------------------------------\n"
    await update.message.reply_html(response_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to show bot statistics."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    total_users = len(user_accounts)
    stats_text = f"<b>Bot Statistics</b>\n\n"
    stats_text += f"Total Active Users: {total_users}\n"
    await update.message.reply_html(stats_text)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to broadcast a message to all users."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Please provide a message to broadcast. Usage: /broadcast [Your message here]")
        return
    
    message_to_send = " ".join(context.args)
    if not user_accounts:
        await update.message.reply_text("No users to broadcast to.")
        return
        
    for telegram_id in user_accounts:
        try:
            await context.bot.send_message(chat_id=telegram_id, text=f"<b>📢 Broadcast Message:</b>\n{message_to_send}", parse_mode="HTML")
        except Exception as e:
            logging.error(f"Failed to send broadcast to user {telegram_id}: {e}")
    
    await update.message.reply_text("Broadcast message sent successfully to all active users.")

async def delete_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to delete a specific user's temporary account."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    # The user ID to delete is expected as an argument after the command
    if not context.args:
        await update.message.reply_text("Please provide a user ID to delete. Usage: /delete_account `[user_id]`")
        return

    try:
        target_user_id = int(context.args[0])
        if target_user_id in user_accounts:
            account = user_accounts[target_user_id]
            # Call the delete method from the pymailtm library
            is_deleted = account.delete_account()
            if is_deleted:
                del user_accounts[target_user_id]
                await update.message.reply_text(f"Account for user ID <code>{target_user_id}</code> deleted successfully.")
            else:
                await update.message.reply_text(f"Failed to delete the account for user ID <code>{target_user_id}</code>.")
        else:
            await update.message.reply_text(f"User ID <code>{target_user_id}</code> not found or has no active account.")
    except (ValueError, KeyError) as e:
        await update.message.reply_text("Invalid user ID provided.")
        logging.error(f"Error deleting account: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a help message with all available commands."""
    help_text = (
        "<b>Available Commands:</b>\n"
        "• /start - Start the bot and get a welcome message.\n"
        "• /new_email - Get a new temporary email address.\n"
        "• /check_inbox - Check your inbox for new messages.\n"
        "• /my_email - See your current email address.\n"
        "• /help - Display this help message.\n\n"
        "For bot administration, if you are the admin, use /admin."
    )
    await update.message.reply_html(help_text)

# The main function to set up and run the bot
def main():
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new_email", new_email_command))
    application.add_handler(CommandHandler("check_inbox", check_inbox_command))
    application.add_handler(CommandHandler("my_email", my_email_command))
    
    # Register admin-specific command handlers
    application.add_handler(CommandHandler("admin", admin_panel_command))
    application.add_handler(CommandHandler("get_all_users", get_all_users_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("delete_account", delete_account_command))
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
