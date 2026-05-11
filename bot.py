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

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

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
# MEMORY
# =========================
data = load_data()

warnings = defaultdict(list, {
    int(k): v
    for k, v in data.get("warnings", {}).items()
})

restrict_data = {
    int(k): v
    for k, v in data.get("restrict_data", {}).items()
}

whitelist = set(data.get("whitelist", []))

# =========================
# SAVE DATA
# =========================
def save_data():

    data = {
        "warnings": dict(warnings),
        "restrict_data": restrict_data,
        "whitelist": list(whitelist)
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# =========================
# ADMIN PERMISSION
# =========================
def has_permission(member: discord.Member):

    admin_role = discord.utils.get(
        member.guild.roles,
        name=ADMIN_ROLE_NAME
    )

    return (
        admin_role in member.roles
        or member.guild_permissions.administrator
        or member.id in whitelist
    )

# =========================
# SUPER PERMISSION
# =========================
def has_super_permission(member: discord.Member):

    admin_role = discord.utils.get(
        member.guild.roles,
        name=ADMIN_ROLE_NAME
    )

    super_role = discord.utils.get(
        member.guild.roles,
        name=SUPER_ROLE_NAME
    )

    return (
        admin_role in member.roles
        or super_role in member.roles
        or member.guild_permissions.administrator
        or member.id in whitelist
    )

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
        print("❌ Sync Error:", e)

    if not auto_unrestrict.is_running():
        auto_unrestrict.start()

# =========================
# WARN
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

    # =========================
    # MUTE
    # =========================
    if total == 2:

        role = discord.utils.get(
            message.guild.roles,
            name=MUTED_ROLE_NAME
        )

        if role:

            await message.author.add_roles(role)

            try:
                await message.author.send(
                    "🔇 Bạn đã bị mute 5 phút vì vi phạm nhiều lần."
                )
            except:
                pass

            async def unmute():

                await asyncio.sleep(300)

                try:
                    await message.author.remove_roles(role)

                    try:
                        await message.author.send(
                            "✅ Bạn đã được unmute."
                        )
                    except:
                        pass

                except:
                    pass

            bot.loop.create_task(unmute())

    # =========================
    # RESTRICT
    # =========================
    elif total >= 3:

        role = discord.utils.get(
            message.guild.roles,
            name=RESTRICT_ROLE_NAME
        )

        if role:

            await message.author.add_roles(role)

            restrict_data[message.author.id] = {
                "expire": (
                    datetime.utcnow() + timedelta(days=1)
                ).isoformat()
            }

            save_data()

            try:
                await message.author.send(
                    "🚫 Bạn đã bị restrict 1 ngày vì vi phạm quá nhiều."
                )
            except:
                pass

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

            add_warn(
                message.author.id,
                f"Dùng từ cấm: {word}",
                "System"
            )

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

    for guild in bot.guilds:

        role = discord.utils.get(
            guild.roles,
            name=RESTRICT_ROLE_NAME
        )

        if not role:
            continue

        now = datetime.utcnow()

        remove_list = []

        for uid, info in restrict_data.items():

            expire = datetime.fromisoformat(
                info["expire"]
            )

            if now >= expire:

                member = guild.get_member(uid)

                if member:

                    try:
                        await member.remove_roles(role)

                        try:
                            await member.send(
                                "✅ Restrict của bạn đã hết hạn."
                            )
                        except:
                            pass

                    except:
                        pass

                remove_list.append(uid)

        for uid in remove_list:
            restrict_data.pop(uid, None)

        save_data()

# =========================
# ROLE ACTION
# =========================
async def role_action(
    interaction,
    member,
    role_name,
    add
):

    role = discord.utils.get(
        interaction.guild.roles,
        name=role_name
    )

    if not role:

        return await interaction.response.send_message(
            "❌ Không tìm thấy role",
            ephemeral=True
        )

    if add:
        await member.add_roles(role)
    else:
        await member.remove_roles(role)

# =========================
# ROLE COMMAND
# =========================
@bot.tree.command(name="role")
@app_commands.describe(
    action="add/remove"
)
@app_commands.choices(action=[
    app_commands.Choice(
        name="Add",
        value="add"
    ),
    app_commands.Choice(
        name="Remove",
        value="remove"
    )
])
async def role_cmd(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member,
    role: discord.Role
):

    if not has_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    if action.value == "add":

        await member.add_roles(role)

        msg = "✅ Đã thêm role"

    else:

        await member.remove_roles(role)

        msg = "❌ Đã gỡ role"

    await interaction.response.send_message(msg)

# =========================
# ADMIN
# =========================
@bot.tree.command(name="admin")
@app_commands.choices(action=[
    app_commands.Choice(
        name="Add",
        value="add"
    ),
    app_commands.Choice(
        name="Remove",
        value="remove"
    )
])
async def admin(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    await role_action(
        interaction,
        member,
        ADMIN_ROLE_NAME,
        action.value == "add"
    )

    await interaction.response.send_message(
        "👑 Done"
    )

# =========================
# SUPER MEMBER
# =========================
@bot.tree.command(name="supermember")
@app_commands.choices(action=[
    app_commands.Choice(
        name="Add",
        value="add"
    ),
    app_commands.Choice(
        name="Remove",
        value="remove"
    )
])
async def supermember(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    await role_action(
        interaction,
        member,
        SUPER_ROLE_NAME,
        action.value == "add"
    )

    await interaction.response.send_message(
        "🌟 Done"
    )

# =========================
# MUTE
# =========================
@bot.tree.command(name="mute")
@app_commands.choices(action=[
    app_commands.Choice(
        name="Add",
        value="add"
    ),
    app_commands.Choice(
        name="Remove",
        value="remove"
    )
])
async def mute(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    await role_action(
        interaction,
        member,
        MUTED_ROLE_NAME,
        action.value == "add"
    )

    await interaction.response.send_message(
        "🔇 Done"
    )

# =========================
# WHITELIST
# =========================
@bot.tree.command(name="whitelist")
@app_commands.choices(action=[
    app_commands.Choice(
        name="Add",
        value="add"
    ),
    app_commands.Choice(
        name="Remove",
        value="remove"
    )
])
async def whitelist_cmd(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_super_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    if action.value == "add":
        whitelist.add(member.id)
    else:
        whitelist.discard(member.id)

    save_data()

    await interaction.response.send_message(
        "✅ Done"
    )

# =========================
# RESTRICT
# =========================
@bot.tree.command(name="restrict")
@app_commands.choices(action=[
    app_commands.Choice(
        name="Add",
        value="add"
    ),
    app_commands.Choice(
        name="Remove",
        value="remove"
    )
])
async def restrict(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member,
    days: int = 1
):

    if not has_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    role = discord.utils.get(
        interaction.guild.roles,
        name=RESTRICT_ROLE_NAME
    )

    if not role:

        return await interaction.response.send_message(
            "❌ Không tìm thấy role",
            ephemeral=True
        )

    if action.value == "add":

        await member.add_roles(role)

        restrict_data[member.id] = {
            "expire": (
                datetime.utcnow() +
                timedelta(days=days)
            ).isoformat()
        }

    else:

        await member.remove_roles(role)

        restrict_data.pop(member.id, None)

    save_data()

    await interaction.response.send_message(
        "🔒 Done"
    )

# =========================
# WARN
# =========================
@bot.tree.command(name="warn")
@app_commands.choices(action=[
    app_commands.Choice(
        name="View",
        value="view"
    ),
    app_commands.Choice(
        name="Clear",
        value="clear"
    )
])
async def warn(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member = None
):

    if action.value == "view":

        target = member or interaction.user

        data = warnings.get(target.id, [])

        if not data:
            text = "No warn"

        else:

            text = "\n".join([
                f"{i+1}. "
                f"{w['reason']} | "
                f"{w['admin']} | "
                f"{w['date']}"
                for i, w in enumerate(data)
            ])

        return await interaction.response.send_message(
            text,
            ephemeral=True
        )

    if not has_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ No permission",
            ephemeral=True
        )

    if not member:

        return await interaction.response.send_message(
            "❌ Chọn member",
            ephemeral=True
        )

    warnings[member.id] = []

    save_data()

    await interaction.response.send_message(
        "⚠️ Cleared"
    )

# =========================
# CLEAR
# =========================
@bot.tree.command(name="clear")
async def clear(
    interaction: discord.Interaction,
    amount: int
):

    if not has_super_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ No permission",
            ephemeral=True
        )

    await interaction.response.defer(
        ephemeral=True
    )

    await interaction.channel.purge(
        limit=amount
    )

    await interaction.followup.send(
        f"🗑️ Đã xóa {amount} tin nhắn",
        ephemeral=True
    )

# =========================
# AVATAR
# =========================
@bot.tree.command(name="avatar")
async def avatar(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    if not has_super_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    member = member or interaction.user

    embed = discord.Embed(
        title=f"Avatar của {member}",
        color=discord.Color.blue()
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )

# =========================
# DM MESSAGE
# =========================
@bot.tree.command(name="dm")
@app_commands.describe(
    member="Người nhận",
    message="Nội dung"
)
async def dm(
    interaction: discord.Interaction,
    member: discord.Member,
    message: str
):

    if not has_permission(interaction.user):

        return await interaction.response.send_message(
            "❌ Không có quyền",
            ephemeral=True
        )

    try:

        embed = discord.Embed(
            title="📩 Bạn có tin nhắn mới",
            description=message,
            color=discord.Color.blue()
        )

        embed.set_footer(
            text=f"Gửi bởi {interaction.user}"
        )

        await member.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Đã gửi DM cho {member.mention}",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ User đã tắt DM",
            ephemeral=True
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ Lỗi: {e}",
            ephemeral=True
        )

# =========================
# START BOT
# =========================
bot.run(
    os.getenv("DISCORD_TOKEN")
)
