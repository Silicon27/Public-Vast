import discord
from discord.ext import commands, tasks
from discord import Embed
from discord_slash import SlashCommand, SlashContext
from github import Github
from urllib.parse import urlparse
import os
import tempfile


intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="/", intents=intents)
slash = SlashCommand(bot, sync_commands=True)
github_update_channels = {}

# Dictionary to store the latest commit SHA for each repository
latest_commit_shas = {}

# GitHub personal access token
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
github = Github(GITHUB_TOKEN)

# Bot token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'BOT_ID')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    check_github_updates.start()

# Command to set the channel for GitHub updates for a specific GitHub username
@slash.slash(name='setup_github_updates', description="Set the channel for GitHub updates")
async def setup_github_updates(ctx, channel: discord.TextChannel, github_username: str):
    github_update_channels[channel.id] = github_username
    await ctx.send(f'GitHub updates for {github_username} will be posted in {channel.mention}')

# Task to check for GitHub updates
@tasks.loop(seconds=60)
async def check_github_updates():
    if not github_update_channels:
        return

    for channel_id, github_username in github_update_channels.items():
        channel = bot.get_channel(channel_id)
        if channel is None:
            continue

        user = github.get_user(github_username)
        for repo in user.get_repos():
            print(f"Checking for changes in repository: {repo.full_name}")
            default_branch = repo.default_branch
            latest_commit = repo.get_commit(sha=default_branch).sha

            # Check for new commits
            if repo.full_name not in latest_commit_shas or latest_commit_shas[repo.full_name] != latest_commit:
                commit = repo.get_commit(sha=latest_commit)
                author = commit.commit.author.name
                url = commit.html_url
                message = commit.commit.message

                embed = Embed(
                    title=f"New Commit in {repo.full_name}",
                    description=message,
                    url=url,
                    color=0x00ff00
                )
                embed.set_author(name=author)
                await channel.send(embed=embed)

                latest_commit_shas[repo.full_name] = latest_commit

@slash.slash(name='get_file', description="Get the contents of a file from a repository")
async def get_file(ctx: SlashContext, repo_url: str, file_path: str):
    try:
        # Parse the provided GitHub URL
        parsed_url = urlparse(repo_url)

        # Check if the URL is from GitHub
        if parsed_url.netloc != 'github.com':
            await ctx.send("Invalid GitHub URL.")
            return

        # Split the URL to get owner and repo name
        owner, repo_name = parsed_url.path.strip('/').split('/')

        # Initialize the GitHub object
        g = Github(GITHUB_TOKEN)

        repo = g.get_repo(f"{owner}/{repo_name}")

        file_content = repo.get_contents(file_path).decoded_content.decode()

        file_extension = os.path.splitext(file_path)[1]

        # Create a temporary file with the extracted extension
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            # Write the received code to the temporary file
            temp_file.write(file_content.encode())

        # Send the temporary file as an attachment
        with open(temp_file.name, 'rb') as file:
            await ctx.send(file=discord.File(file))

        # Delete the temporary file
        os.remove(temp_file.name)
    except Exception as e:
        await ctx.send(f'Error: {e}')

@slash.slash(name='ping', description="Check the bot's latency")
async def ping(ctx):
    latency = bot.latency * 1000  # Convert latency to milliseconds
    await ctx.send(f'Pong! Latency: {latency:.2f} ms')

# Run the bot with the token
if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("Error: DISCORD_TOKEN is not set.")
