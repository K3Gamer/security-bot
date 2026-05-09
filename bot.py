import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import json
import os

# =========================
# CONFIG
# =========================

RESTRICT_ROLE_NAME = "🚫Restricted"
ADMIN_ROLE_NAME = "👑Admin"
SUPER_ROLE_NAME = "🌟Super Member"
MUTED_ROLE_NAME = "🔇Muted"

BAD_WORDS = [
    "địt", "dm", "dmm", "cc", "cặc", "lồn",
    "đụ", "ngu", "óc chó", "sybau",
    "bitch", "fuck"
]

# =========================
# INTENTS
# =========================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATA FILE
# =========================
DATA_FILE = "data.json"


# =========================
# LOAD DATA
# =========================
def load_data():
    if not os.path.exists(DATA_FILE):
        default = {
            "warnings": {},
            "restrict_data": {},
            "whitelist": []
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# SAVE DATA
# =========================
def save_data():
    data = {
        "warnings": warnings,
        "restrict_data": restrict_data,
        "whitelist": list(whitelist)
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# =========================
# MEMORY
# =========================
data = load_data()

warnings = defaultdict(list, {
    int(k): v for k, v in data.get("warnings", {}).items()
})

restrict_data = {
    int(k): v for k, v in data.get("restrict_data", {}).items()
}

whitelist = set(data.get("whitelist", []))


# =========================
# PERMISSION CHECK
# =========================
def has_permission(member: discord.Member):
    admin_role = discord.utils.get(member.guild.roles, name=ADMIN_ROLE_NAME)

    return (admin_role in member.roles) or (member.id in whitelist)


# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print("Sync error:", e)

    if not auto_unrestrict.is_running():
        auto_unrestrict.start()


# =========================
# SAVE WARN
# =========================
def add_warn(user_id, reason, admin):
    warnings[user_id].append({
        "reason": reason,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "admin": admin
    })
    save_data()


# =========================
# AUTO PUNISH
# =========================
async def auto_punish(message):
    total = len(warnings[message.author.id])

    # MUTE 2 WARN
    if total == 2:
        role = discord.utils.get(message.guild.roles, name=MUTED_ROLE_NAME)

        if role:
            await message.author.add_roles(role)

            async def unmute():
                await asyncio.sleep(300)
                await message.author.remove_roles(role)

            bot.loop.create_task(unmute())

    # RESTRICT 3 WARN
    elif total >= 3:
        role = discord.utils.get(message.guild.roles, name=RESTRICT_ROLE_NAME)

        if role:
            await message.author.add_roles(role)

            restrict_data[message.author.id] = {
                "expire": (datetime.utcnow() + timedelta(days=1)).isoformat()
            }
            save_data()


# =========================
# MESSAGE FILTER
# =========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    for word in BAD_WORDS:
        if word in content:

            try:
                await message.delete()
            except:
                pass

            add_warn(message.author.id, f"Dùng từ cấm: {word}", "System")

            await auto_punish(message)

            await message.channel.send(
                f"⚠️ {message.author.mention} vi phạm nội dung!",
                delete_after=5
            )
            return

    await bot.process_commands(message)


# =========================
# AUTO UNRESTRICT
# =========================
@tasks.loop(minutes=1)
async def auto_unrestrict():
    if not bot.guilds:
        return

    guild = bot.guilds[0]
    role = discord.utils.get(guild.roles, name=RESTRICT_ROLE_NAME)

    if not role:
        return

    now = datetime.utcnow()
    remove = []

    for uid, info in restrict_data.items():
        expire = datetime.fromisoformat(info["expire"])

        if now >= expire:
            member = guild.get_member(uid)

            if member:
                try:
                    await member.remove_roles(role)
                except:
                    pass

            remove.append(uid)

    for uid in remove:
        del restrict_data[uid]
        save_data()


# =========================
# ROLE COMMAND
# =========================
@bot.tree.command(name="role")
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove")
])
async def role_cmd(interaction: discord.Interaction, action: app_commands.Choice[str], member: discord.Member, role: discord.Role):

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ Không có quyền", ephemeral=True)

    if action.value == "add":
        await member.add_roles(role)
        save_data()
        await interaction.response.send_message("✅ Đã thêm role")

    else:
        await member.remove_roles(role)
        await interaction.response.send_message("❌ Đã gỡ role")


# =========================
# ADMIN / SUPER / MUTE / WHITELIST
# =========================
async def role_action(interaction, member, role_name, add):
    role = discord.utils.get(interaction.guild.roles, name=role_name)
    if not role:
        return

    if add:
        await member.add_roles(role)
    else:
        await member.remove_roles(role)


@bot.tree.command(name="admin")
async def admin(interaction, action: app_commands.Choice[str], member: discord.Member):

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ Không có quyền", ephemeral=True)

    await role_action(interaction, member, ADMIN_ROLE_NAME, action.value == "add")
    await interaction.response.send_message("👑 Done")


@bot.tree.command(name="supermember")
async def super(interaction, action: app_commands.Choice[str], member: discord.Member):

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ Không có quyền", ephemeral=True)

    await role_action(interaction, member, SUPER_ROLE_NAME, action.value == "add")
    await interaction.response.send_message("🌟 Done")


@bot.tree.command(name="mute")
async def mute(interaction, action: app_commands.Choice[str], member: discord.Member):

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ Không có quyền", ephemeral=True)

    await role_action(interaction, member, MUTED_ROLE_NAME, action.value == "add")
    await interaction.response.send_message("🔇 Done")


@bot.tree.command(name="whitelist")
async def whitelist_cmd(interaction, action: app_commands.Choice[str], member: discord.Member):

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ Không có quyền", ephemeral=True)

    if action.value == "add":
        whitelist.add(member.id)
    else:
        whitelist.discard(member.id)

    save_data()
    await interaction.response.send_message("✅ Done")


# =========================
# RESTRICT
# =========================
@bot.tree.command(name="restrict")
async def restrict(interaction, action: app_commands.Choice[str], member: discord.Member, days: int = 1):

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ Không có quyền", ephemeral=True)

    role = discord.utils.get(interaction.guild.roles, name=RESTRICT_ROLE_NAME)

    if action.value == "add":
        await member.add_roles(role)

        restrict_data[member.id] = {
            "expire": (datetime.utcnow() + timedelta(days=days)).isoformat()
        }

        save_data()

    else:
        await member.remove_roles(role)
        restrict_data.pop(member.id, None)
        save_data()

    await interaction.response.send_message("🔒 Done")


# =========================
# WARN SYSTEM
# =========================
@bot.tree.command(name="warn")
async def warn(interaction, action: app_commands.Choice[str], member: discord.Member = None):

    if action.value == "view":
        target = member or interaction.user
        data = warnings.get(target.id, [])

        return await interaction.response.send_message(
            "\n".join([f"{w['reason']} - {w['admin']}" for w in data]) or "No warn",
            ephemeral=True
        )

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ No permission", ephemeral=True)

    if action.value == "clear":
        warnings[member.id] = []
        save_data()

    await interaction.response.send_message("⚠️ Done")


# =========================
# UTILS
# =========================
@bot.tree.command(name="clear")
async def clear(interaction, amount: int):

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ No permission", ephemeral=True)

    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message("🗑️ Cleared", ephemeral=True)


@bot.tree.command(name="avatar")
async def avatar(interaction, member: discord.Member = None):

    member = member or interaction.user

    embed = discord.Embed(title="Avatar")
    embed.set_image(url=member.display_avatar.url)

    await interaction.response.send_message(embed=embed)


# =========================
# START BOT
# =========================
bot.run(os.getenv("DISCORD_TOKEN"))
