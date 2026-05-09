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
    "địt",
    "dm",
    "dmm",
    "cc",
    "cặc",
    "lồn",
    "đụ",
    "ngu",
    "óc chó",
    "sybau",
    "bitch",
    "fuck",
    "gay",
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

        default_data = {
            "warnings": {},
            "restrict_data": {},
            "whitelist": []
        }

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                default_data,
                f,
                indent=4
            )

    with open(DATA_FILE, "r", encoding="utf-8") as f:

        data = json.load(f)

    return data

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

        json.dump(
            data,
            f,
            indent=4,
            default=str
        )

# =========================
# LOAD INTO MEMORY
# =========================
data = load_data()

warnings = defaultdict(
    list,
    {
        int(k): v
        for k, v in data.get(
            "warnings",
            {}
        ).items()
    }
)

restrict_data = {
    int(k): v
    for k, v in data.get(
        "restrict_data",
        {}
    ).items()
}

whitelist = set(
    data.get(
        "whitelist",
        []
    )
)

# =========================
# PERMISSION CHECK
# =========================
def has_permission(member: discord.Member):

    admin_role = discord.utils.get(
        member.guild.roles,
        name=ADMIN_ROLE_NAME
    )

    if admin_role in member.roles:
        return True

    if member.id in whitelist:
        return True

    return False

# =========================
# READY
# =========================
@bot.event
async def on_ready():

    print(f"✅ Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")

    except Exception as e:
        print("❌ Slash Sync Error:", e)

    if not auto_unrestrict.is_running():
        auto_unrestrict.start()

# =========================
# AUTO PUNISH
# =========================
async def auto_punish(message):

    total_warns = len(
        warnings[message.author.id]
    )

    # =========================
    # 2 WARN = MUTE 5 PHÚT
    # =========================
    if total_warns == 2:

        muted_role = discord.utils.get(
            message.guild.roles,
            name=MUTED_ROLE_NAME
        )

        if muted_role:

            try:

                await message.author.add_roles(
                    muted_role
                )

                await message.channel.send(
                    f"🔇 {message.author.mention} "
                    f"đã bị mute 5 phút vì đủ 2 warn."
                )

                async def remove_mute():

                    await asyncio.sleep(300)

                    try:
                        await message.author.remove_roles(
                            muted_role
                        )
                    except:
                        pass

                bot.loop.create_task(
                    remove_mute()
                )

            except:
                pass

    # =========================
    # 3 WARN = RESTRICT
    # =========================
    elif total_warns >= 3:

        restrict_role = discord.utils.get(
            message.guild.roles,
            name=RESTRICT_ROLE_NAME
        )

        if restrict_role:

            try:

                await message.author.add_roles(
                    restrict_role
                )

                expire = datetime.utcnow() + timedelta(
                    days=1
                )

                restrict_data[message.author.id] = {
                    "expire": expire
                }

                await message.channel.send(
                    f"🔒 {message.author.mention} "
                    f"đã bị restrict 1 ngày vì đủ 3 warn."
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

    # =========================
    # BAD WORD FILTER
    # =========================
    for word in BAD_WORDS:

        if word in content:

            try:
                await message.delete()
            except:
                pass

            warnings[message.author.id].append({
                "reason": f"Dùng từ cấm: {word}",
                "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "admin": "System"
                
            })
            save_data()
            await auto_punish(message)

            try:
                await message.channel.send(
                    f"⚠️ {message.author.mention}, không được dùng từ cấm!",
                    delete_after=5
                )
            except:
                pass

            return
    await bot.process_commands(message)

# =========================
# ROLE
# =========================
@bot.tree.command(name="role")
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove")
])
async def role(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member,
    role: discord.Role
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    if action.value == "add":

        await member.add_roles(role)
        save_data()
        await interaction.response.send_message(
            f"✅ Đã thêm {role.mention}"
        )

    elif action.value == "remove":

        await member.remove_roles(role)

        await interaction.response.send_message(
            f"❌ Đã gỡ {role.mention}"
        )

# =========================
# ADMIN
# =========================
@bot.tree.command(name="admin")
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove")
])
async def admin(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    role = discord.utils.get(
        interaction.guild.roles,
        name=ADMIN_ROLE_NAME
    )

    if role is None:
        return

    if action.value == "add":

        await member.add_roles(role)

        await interaction.response.send_message(
            f"👑 Đã cấp admin"
        )

    elif action.value == "remove":

        await member.remove_roles(role)

        await interaction.response.send_message(
            f"❌ Đã gỡ admin"
        )

# =========================
# SUPER MEMBER
# =========================
@bot.tree.command(name="supermember")
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove")
])
async def supermember(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    role = discord.utils.get(
        interaction.guild.roles,
        name=SUPER_ROLE_NAME
    )

    if role is None:
        return

    if action.value == "add":

        await member.add_roles(role)

        await interaction.response.send_message(
            f"🌟 Đã cấp Super Member"
        )

    elif action.value == "remove":

        await member.remove_roles(role)

        await interaction.response.send_message(
            f"❌ Đã gỡ Super Member"
        )

# =========================
# WHITELIST
# =========================
@bot.tree.command(name="whitelist")
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove")
])
async def whitelist_cmd(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    if action.value == "add":

        whitelist.add(member.id)

        await interaction.response.send_message(
            f"✅ Đã whitelist"
        )

    elif action.value == "remove":

        whitelist.discard(member.id)

        await interaction.response.send_message(
            f"❌ Đã gỡ whitelist"
        )
    save_data()
# =========================
# RESTRICT
# =========================
@bot.tree.command(name="restrict")
@app_commands.choices(action=[
    app_commands.Choice(name="Restrict", value="add"),
    app_commands.Choice(name="Unrestrict", value="remove")
])
async def restrict(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member,
    days: int = 1,
    reason: str = "Không có"
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    role = discord.utils.get(
        interaction.guild.roles,
        name=RESTRICT_ROLE_NAME
    )

    if role is None:
        return

    if action.value == "add":

        await member.add_roles(role)

        expire = datetime.utcnow() + timedelta(
            days=days
        )

        restrict_data[member.id] = {
            "expire": expire.isoformat()
        }
        save_data()

        warnings[member.id].append({
            "reason": f"Restrict: {reason}",
            "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "admin": interaction.user.name
        })

        await interaction.response.send_message(
            f"🔒 Đã restrict {member.mention}"
        )

    elif action.value == "remove":

        await member.remove_roles(role)

        if member.id in restrict_data:
            del restrict_data[member.id]

        await interaction.response.send_message(
            f"🔓 Đã unrestrict"
        )

# =========================
# MUTE
# =========================
@bot.tree.command(name="mute")
@app_commands.choices(action=[
    app_commands.Choice(name="Mute", value="add"),
    app_commands.Choice(name="Unmute", value="remove")
])
async def mute(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    role = discord.utils.get(
        interaction.guild.roles,
        name=MUTED_ROLE_NAME
    )

    if role is None:
        return

    if action.value == "add":

        await member.add_roles(role)

        await interaction.response.send_message(
            f"🔇 Đã mute"
        )

    elif action.value == "remove":

        await member.remove_roles(role)

        await interaction.response.send_message(
            f"🔊 Đã unmute"
        )
    save_data()
# =========================
# BAN
# =========================
@bot.tree.command(name="ban")
@app_commands.choices(action=[
    app_commands.Choice(name="Ban", value="add"),
    app_commands.Choice(name="Unban", value="remove")
])
async def ban(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member = None,
    user_id: str = None,
    reason: str = "Không có"
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    if action.value == "add":

        if member is None:
            return

        await member.ban(reason=reason)

        await interaction.response.send_message(
            f"🔨 Đã ban"
        )

    elif action.value == "remove":

        if user_id is None:
            return

        user = await bot.fetch_user(
            int(user_id)
        )

        await interaction.guild.unban(user)

        await interaction.response.send_message(
            f"✅ Đã unban"
        )

# =========================
# WARN
# =========================
@bot.tree.command(name="warn")
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove"),
    app_commands.Choice(name="Clear", value="clear"),
    app_commands.Choice(name="View", value="view"),
    app_commands.Choice(name="Top", value="top")
])
async def warn(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    member: discord.Member = None,
    reason: str = "Không có",
    amount: int = 1,
    warn_number: int = 1
):

    action = action.value.lower()

    # VIEW
    if action == "view":

        target = member or interaction.user

        data = warnings.get(
            target.id,
            []
        )

        if not data:

            await interaction.response.send_message(
                "✅ Không có warn",
                ephemeral=True
            )
            return

        text = ""

        for i, warn_data in enumerate(data, start=1):

            text += (
                f"{i}. {warn_data['reason']}\n"
                f"👮 {warn_data['admin']}\n"
                f"📅 {warn_data['date']}\n\n"
            )

        await interaction.response.send_message(
            f"```{text[:1900]}```",
            ephemeral=True
        )

        return

    # TOP
    if action == "top":

        sorted_warns = sorted(
            warnings.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        text = ""

        for i, (user_id, warns) in enumerate(sorted_warns[:10], start=1):

            member_obj = interaction.guild.get_member(
                user_id
            )

            if member_obj:

                text += (
                    f"{i}. {member_obj.name} "
                    f"- {len(warns)} warn\n"
                )

        await interaction.response.send_message(
            f"```{text or 'Không có dữ liệu'}```"
        )

        return

    # ADMIN CHECK
    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    if member is None:
        return

    # ADD WARN
    if action == "add":

        for i in range(amount):

            warnings[member.id].append({
                "reason": reason,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "admin": interaction.user.name
            })

        await interaction.response.send_message(
            f"⚠️ Đã warn {member.mention}"
        )
        save_data()    
    # REMOVE WARN
    elif action == "remove":

        data = warnings.get(
            member.id,
            []
        )

        if warn_number < 1 or warn_number > len(data):
            return

        data.pop(warn_number - 1)

        await interaction.response.send_message(
            f"🗑️ Đã xóa warn"
        )
        save_data()
    # CLEAR WARN
    elif action == "clear":

        warnings[member.id] = []

        await interaction.response.send_message(
            f"✅ Đã clear warn"
        )
        save_data()
# =========================
# CHAT
# =========================
@bot.tree.command(name="chat")
async def chat(
    interaction: discord.Interaction,
    message: str
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "✅ Đã gửi",
        ephemeral=True
    )

    await interaction.channel.send(message)

# =========================
# TIMEOUT
# =========================
@bot.tree.command(name="timeout")
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: int,
    reason: str = "Không có"
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    until = discord.utils.utcnow() + timedelta(
        minutes=minutes
    )

    await member.timeout(
        until,
        reason=reason
    )

    await interaction.response.send_message(
        f"⏳ Đã timeout"
    )

# =========================
# KICK
# =========================
@bot.tree.command(name="kick")
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "Không có"
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    await member.kick(reason=reason)

    await interaction.response.send_message(
        f"👢 Đã kick"
    )

# =========================
# CLEAR
# =========================
@bot.tree.command(name="clear")
async def clear(
    interaction: discord.Interaction,
    amount: int
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    await interaction.response.defer(
        ephemeral=True
    )

    deleted = await interaction.channel.purge(
        limit=amount
    )

    await interaction.followup.send(
        f"🗑️ Đã xóa {len(deleted)} tin nhắn",
        ephemeral=True
    )

# =========================
# LOCK
# =========================
@bot.tree.command(name="lock")
async def lock(
    interaction: discord.Interaction,
    state: bool
):

    if not has_permission(interaction.user):

        await interaction.response.send_message(
            "❌ Không có quyền!",
            ephemeral=True
        )
        return

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = not state

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    if state:

        await interaction.response.send_message(
            "🔒 Đã khóa channel"
        )

    else:

        await interaction.response.send_message(
            "🔓 Đã mở khóa channel"
        )

# =========================
# AVATAR
# =========================
@bot.tree.command(name="avatar")
async def avatar(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = member or interaction.user

    embed = discord.Embed(
        title=f"Avatar của {member.name}"
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )

# =========================
# AUTO UNRESTRICT
# =========================
@tasks.loop(minutes=1)
async def auto_unrestrict():

    if not bot.guilds:
        return

    guild = bot.guilds[0]

    role = discord.utils.get(
        guild.roles,
        name=RESTRICT_ROLE_NAME
    )

    if role is None:
        return

    now = datetime.utcnow()

    remove_list = []

    for user_id, info in restrict_data.items():

        expire = info["expire"]
        
        if isinstance(expire, str):
            expire = datetime.fromisoformat(expire)
        
        if now >= expire:

            member = guild.get_member(
                user_id
            )

            if member:

                try:
                    await member.remove_roles(role)
                except:
                    pass

            remove_list.append(user_id)
    
    for uid in remove_list:
        del restrict_data[uid]
        save_data()
    save_data()
# =========================
# START BOT
# =========================
bot.run(os.getenv("DISCORD_TOKEN"))
