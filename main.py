import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput, Button
import io
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import json
import os
import chat_exporter


HEADS_ROLE_ID = 
STAFF_ROLE_ID = 


CATEGORY_IDS = {
    "soporte": ,
    "reportes": ,
    "tienda": ,
    "media": ,
    "apelacion": ,
    "administracion": ,
}


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, activity=discord.Game(name="ytopensourcebot.net"))
        self.transcript_channel_id = None
        self.welcome_channel_id = None
        self.ticket_stats = {}
        self.ticket_owners = {}
        
    async def setup_hook(self):
        self.add_view(TicketSelectView())
        self.add_view(TicketControlView())
        await self.tree.sync()
        print("Bot iniciado correctamente")


bot = MyBot()


def check_heads():
    """Decorator para verificar si el usuario tiene rol Heads o es administrador"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        heads_role = interaction.guild.get_role(HEADS_ROLE_ID)
        if heads_role and heads_role in interaction.user.roles:
            return True
        return False
    return app_commands.check(predicate)


def check_staff():
    """Decorator para verificar si el usuario tiene rol Staff, Heads o es administrador"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        heads_role = interaction.guild.get_role(HEADS_ROLE_ID)
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        user_roles = interaction.user.roles
        if (heads_role and heads_role in user_roles) or (staff_role and staff_role in user_roles):
            return True
        return False
    return app_commands.check(predicate)


async def create_welcome_image(member: discord.Member):
    """Crea imagen de bienvenida con avatar del miembro"""
    try:
        avatar_url = member.display_avatar.url
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                avatar_data = await resp.read()


        img = Image.new('RGB', (800, 400), color=(47, 49, 54))
        draw = ImageDraw.Draw(img)


        avatar = Image.open(io.BytesIO(avatar_data)).convert('RGBA')
        avatar = avatar.resize((200, 200), Image.Resampling.LANCZOS)


        mask = Image.new('L', (200, 200), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 200, 200), fill=255)


        img.paste(avatar, (300, 80), mask)


        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        except:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()


        username = member.name
        bbox = draw.textbbox((0, 0), username, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text((400 - text_width/2, 300), username, fill=(255, 255, 255), font=font)


        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Error creando imagen: {e}")
        return None



class TicketFormModal(Modal, title="Formulario de Ticket"):
    nombre = TextInput(
        label="¿Cuál es tu Nick?",
        placeholder="Ingresa tu nombre/nick",
        required=True,
        max_length=100
    )
    
    problema = TextInput(
        label="¿Cuál es tu duda?",
        placeholder="Describe tu problema o duda con detalles",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    def __init__(self, category: str, original_message: discord.Message):
        super().__init__()
        self.category = category
        self.original_message = original_message
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        user = interaction.user
        
        category_prefix = {
            "🔩 Soporte": "soporte",
            "📚 Reportes bugs/users": "reportes",
            "🛒 Tienda": "tienda",
            "🎬 Media": "mediapost",
            "🔧 Apelacion": "apelacion",
            "🤔 Administracion": "administracion"
        }
        
        prefix = category_prefix.get(self.category, "ticket")
        
        all_prefixes = ["soporte", "reportes", "tienda", "mediapost", "apelacion", "administracion"]
        for channel in guild.text_channels:
            for check_prefix in all_prefixes:
                if channel.name.startswith(f"{check_prefix}-{user.name.lower()}"):
                    await interaction.followup.send(
                        f"❌ Ya tienes un ticket abierto: {channel.mention}\nCiérralo antes de abrir uno nuevo.", 
                        ephemeral=True
                    )
                    try:
                        await self.original_message.edit(view=TicketSelectView())
                    except:
                        pass
                    return
        
        category_mapping = {
            "🔩 Soporte": "soporte",
            "📚 Reportes bugs/users": "reportes",
            "🛒 Tienda": "tienda",
            "🎬 Media": "media",
            "🔧 Apelacion": "apelacion",
            "🤔 Administracion": "administracion"
        }
        
        category_key = category_mapping.get(self.category)
        category_id = CATEGORY_IDS.get(category_key)
        category_obj = guild.get_channel(category_id)
        
        if not category_obj:
            await interaction.followup.send(
                "❌ Error: La categoría no está configurada correctamente.", 
                ephemeral=True
            )
            try:
                await self.original_message.edit(view=TicketSelectView())
            except:
                pass
            return
        
        heads_role = guild.get_role(HEADS_ROLE_ID)
        staff_role = guild.get_role(STAFF_ROLE_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True
            )
        }
        
        if self.category in ["🤔 Administracion", "🛒 Tienda"]:
            if heads_role:
                overwrites[heads_role] = discord.PermissionOverwrite(
                    view_channel=True, 
                    send_messages=True, 
                    read_message_history=True
                )
        else:
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    view_channel=True, 
                    send_messages=True, 
                    read_message_history=True
                )
        
        ticket_name = f"{prefix}-{user.name.lower()}"
        ticket_channel = await category_obj.create_text_channel(
            name=ticket_name,
            overwrites=overwrites
        )
        
        bot.ticket_owners[ticket_channel.id] = {
            "owner": user.id,
            "category": self.category,
            "claimed_by": None
        }
        
        if self.category in ["🤔 Administracion", "🛒 Tienda"]:
            role_mention = heads_role.mention if heads_role else "@Heads"
        else:
            role_mention = staff_role.mention if staff_role else "@Staff"
        
        welcome_message = f"¡Hola! Buenas tardes {user.mention}, bienvenido a tu ticket. Se paciente y no taguees a ningun staff! {role_mention}"
        
        embed = discord.Embed(
            title="BIENVENIDO AL SISTEMA DE TICKETS",
            description=(
                "Bienvenido al sistema de tickets oficial de open Source Bot.\n\n"
                "> En los siguientes minutos seras atendido por un Staff del servidor. Si este no responde, porfavor mantenga la calma.\n\n"
                "> Agradecemos que expliques tu problema con detalles. Aquí está la información que nos has proporcionado:\n\n"
                f"**¿Cuál es tu Nick?**: {self.nombre.value}\n"
                f"**¿Cuál es tu duda?**: {self.problema.value}"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="YT Open Source BOT - Sistema de Tickets")
        
        await ticket_channel.send(welcome_message)
        await ticket_channel.send(embed=embed, view=TicketControlView())
        
        await interaction.followup.send(
            f"✅ Tu ticket ha sido creado: {ticket_channel.mention}", 
            ephemeral=True
        )

        try:
            await self.original_message.edit(view=TicketSelectView())
        except Exception as e:
            print(f"Error al resetear menú: {e}")



class TicketSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="🔩 Soporte",
                description="¿Tienes dudas o necesitas ayuda General?",
                value="soporte",
                emoji="🔩"
            ),
            discord.SelectOption(
                label="📚 Reportes bugs/users",
                description="¿Viste a alguien romper las reglas?",
                value="reportes",
                emoji="📚"
            ),
            discord.SelectOption(
                label="🛒 Tienda",
                description="¿Quieres comprar algun rango?",
                value="tienda",
                emoji="🛒"
            ),
            discord.SelectOption(
                label="🎬 Media",
                description="¿Quieres postularte a media!",
                value="media",
                emoji="🎬"
            ),
            discord.SelectOption(
                label="🔧 Apelacion",
                description="¿Un baneo injusto?",
                value="apelacion",
                emoji="🔧"
            ),
            discord.SelectOption(
                label="🤔 Administracion",
                description="¿Necesitas hablar de algo administrativo?",
                value="administracion",
                emoji="🤔"
            )
        ]
        super().__init__(
            placeholder="Selecciona el tipo de ticket...",
            options=options,
            custom_id="ticket_select_persistent",
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        category_names = {
            "soporte": "🔩 Soporte",
            "reportes": "📚 Reportes bugs/users",
            "tienda": "🛒 Tienda",
            "media": "🎬 Media",
            "apelacion": "🔧 Apelacion",
            "administracion": "🤔 Administracion"
        }
        
        category = category_names.get(self.values[0])
        modal = TicketFormModal(category, interaction.message)
        await interaction.response.send_modal(modal)



class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Reclamar Ticket", style=discord.ButtonStyle.green, custom_id="claim_ticket", emoji="✋")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        heads_role = interaction.guild.get_role(HEADS_ROLE_ID)
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        user_roles = interaction.user.roles
        
        is_staff = (heads_role and heads_role in user_roles) or (staff_role and staff_role in user_roles)
        is_head = heads_role and heads_role in user_roles
        
        if not is_staff and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Solo el staff puede reclamar tickets.", ephemeral=True)
            return
        
        channel_id = interaction.channel.id
        ticket_info = bot.ticket_owners.get(channel_id)
        
        if not ticket_info:
            await interaction.response.send_message("Este canal no es un ticket valido.", ephemeral=True)
            return
        
        if ticket_info["claimed_by"]:
            await interaction.response.send_message("Este ticket ya ha sido reclamado por otro staff.", ephemeral=True)
            return
        
        ticket_info["claimed_by"] = interaction.user.id
        
        if interaction.user.id not in bot.ticket_stats:
            bot.ticket_stats[interaction.user.id] = 0
        bot.ticket_stats[interaction.user.id] += 1
        
        channel = interaction.channel
        ticket_owner_id = ticket_info["owner"]
        ticket_owner = interaction.guild.get_member(ticket_owner_id)
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
        }
        
        if ticket_owner:
            overwrites[ticket_owner] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
        
        if heads_role:
            overwrites[heads_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        
        await channel.edit(overwrites=overwrites)
        
        embed = discord.Embed(
            title="Ticket Reclamado",
            description=f"Este ticket ha sido reclamado por {interaction.user.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="YT Open Source Bot - Sistema de Tickets")
        
        await interaction.response.send_message(embed=embed)
    
    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.red, custom_id="close_ticket", emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        heads_role = interaction.guild.get_role(HEADS_ROLE_ID)
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        user_roles = interaction.user.roles
        
        is_staff = (heads_role and heads_role in user_roles) or (staff_role and staff_role in user_roles)
        
        if not is_staff and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Solo el staff puede cerrar tickets.", ephemeral=True)
            return
        
        if not bot.transcript_channel_id:
            await interaction.response.send_message(
                "El sistema de transcripts no esta activado. Usa /system-transcripts primero.",
                ephemeral=True
            )
            return
        
        transcript_channel = interaction.guild.get_channel(bot.transcript_channel_id)
        if not transcript_channel:
            await interaction.response.send_message(
                "El canal de transcripts no existe. Configuralo de nuevo.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message("Cerrando ticket y generando transcript...", ephemeral=True)
        
        ticket_info = bot.ticket_owners.get(interaction.channel.id)
        ticket_owner = None
        if ticket_info:
            ticket_owner = interaction.guild.get_member(ticket_info["owner"])
        
        try:
            transcript = await chat_exporter.export(interaction.channel)
            
            if transcript:
                transcript_data = transcript.encode()
                
                transcript_file_channel = discord.File(
                    io.BytesIO(transcript_data),
                    filename=f"transcript-{interaction.channel.name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.html"
                )
                
                embed = discord.Embed(
                    title="Transcript de Ticket",
                    description=f"**Ticket:** {interaction.channel.name}\n**Cerrado por:** {interaction.user.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="YT Open Source Bot - Sistema de Tickets")
                
                await transcript_channel.send(embed=embed, file=transcript_file_channel)
                
                embed_dm = discord.Embed(
                    title="Transcript de tu Ticket",
                    description=f"**Ticket:** {interaction.channel.name}\n**Cerrado por:** {interaction.user.name}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed_dm.set_footer(text="YT Open Source Bot - Sistema de Tickets")
                
                if ticket_owner:
                    try:
                        transcript_file_owner = discord.File(
                            io.BytesIO(transcript_data),
                            filename=f"transcript-{interaction.channel.name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.html"
                        )
                        await ticket_owner.send(embed=embed_dm, file=transcript_file_owner)
                    except:
                        pass
                
                try:
                    embed_staff = discord.Embed(
                        title="Transcript del Ticket que cerraste",
                        description=f"**Ticket:** {interaction.channel.name}\n**Usuario:** {ticket_owner.name if ticket_owner else 'Desconocido'}",
                        color=discord.Color.blue(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed_staff.set_footer(text="YT Open Source Bot - Sistema de Tickets")
                    transcript_file_staff = discord.File(
                        io.BytesIO(transcript_data),
                        filename=f"transcript-{interaction.channel.name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.html"
                    )
                    await interaction.user.send(embed=embed_staff, file=transcript_file_staff)
                except:
                    pass
            
            if interaction.channel.id in bot.ticket_owners:
                del bot.ticket_owners[interaction.channel.id]
            
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}")
            
        except Exception as e:
            print(f"Error al cerrar ticket: {e}")
            await interaction.followup.send(f"Error al cerrar el ticket: {str(e)}", ephemeral=True)



@bot.tree.command(name="system-tickets", description="Activa el sistema de tickets en este canal")
@check_heads()
async def system_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Sistema de Tickets - YT Open Source Bot",
        description=(
            "¿Necesitas ayuda? Selecciona una de las opciones según el tipo de asistencia que requieres. "
            "Nuestro equipo te atenderá lo antes posible.\n\n"
            "**Tipos de soporte disponibles:**\n\n"
            "🔩 **General**\nConsultas generales y soporte básico\n\n"
            "🛒 **Tienda**\nProblemas con compras y transacciones\n\n"
            "🎯 **Media**\nReportes de contenido multimedia\n\n"
            "🔧 **Apelación**\nApelaciones de sanciones\n\n"
            "📚 **Reportes bugs/users**\nReportar un bug o usuario\n\n"
            "👑 **Administración**\nTemas Administrativos"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="YT Open Source BotMC - Sistema de Tickets")
    
    await interaction.channel.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message("✅ Sistema de tickets activado correctamente.", ephemeral=True)


@bot.tree.command(name="system-transcripts", description="Configura el canal donde se enviarán las transcripts")
@app_commands.describe(canal="El canal donde se enviarán las transcripts")
@check_heads()
async def system_transcripts(interaction: discord.Interaction, canal: discord.TextChannel):
    bot.transcript_channel_id = canal.id
    await interaction.response.send_message(
        f"✅ Sistema de transcripts activado. Las transcripts se enviarán a {canal.mention}", 
        ephemeral=True
    )


@bot.tree.command(name="ticket-rename", description="Renombra el canal del ticket actual")
@app_commands.describe(nombre="El nuevo nombre del ticket")
@check_staff()
async def ticket_rename(interaction: discord.Interaction, nombre: str):
    if interaction.channel.id not in bot.ticket_owners:
        await interaction.response.send_message("❌ Este comando solo puede usarse en tickets.", ephemeral=True)
        return
    
    try:
        await interaction.channel.edit(name=nombre)
        await interaction.response.send_message(f"✅ Ticket renombrado a: **{nombre}**", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error al renombrar: {str(e)}", ephemeral=True)


@bot.tree.command(name="ticket-add", description="Anade un usuario al ticket actual")
@app_commands.describe(usuario="El usuario a anadir al ticket")
@check_staff()
async def ticket_add(interaction: discord.Interaction, usuario: discord.Member):
    if interaction.channel.id not in bot.ticket_owners:
        await interaction.response.send_message("Este comando solo puede usarse en tickets.", ephemeral=True)
        return
    
    try:
        await interaction.channel.set_permissions(
            usuario,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True
        )
        await interaction.response.send_message(
            f"{usuario.mention} ha sido anadido al ticket.",
            ephemeral=True
        )
        await interaction.channel.send(f"{usuario.mention} ha sido anadido al ticket por {interaction.user.mention}")
    except Exception as e:
        await interaction.response.send_message(f"Error al anadir usuario: {str(e)}", ephemeral=True)


@bot.tree.command(name="top", description="Muestra el top 5 de staffs con mas tickets reclamados")
@check_staff()
async def top_tickets(interaction: discord.Interaction):
    if not bot.ticket_stats:
        await interaction.response.send_message("No hay estadisticas de tickets aun.", ephemeral=True)
        return
    
    sorted_stats = sorted(bot.ticket_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    
    embed = discord.Embed(
        title="🏆 Top 5 Staff - Tickets Reclamados",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for idx, (user_id, count) in enumerate(sorted_stats):
        user = interaction.guild.get_member(user_id)
        if user:
            embed.add_field(
                name=f"{medals[idx]} {user.name}",
                value=f"**{count}** tickets reclamados",
                inline=False
            )
    
    embed.set_footer(text="YT Open Source Bot - Sistema de Tickets")
    
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="system-welcome", description="Activa el sistema de bienvenidas en este canal")
@check_heads()
async def system_welcome(interaction: discord.Interaction):
    bot.welcome_channel_id = interaction.channel.id
    await interaction.response.send_message(
        f"Sistema de bienvenidas activado en {interaction.channel.mention}",
        ephemeral=True
    )



@bot.command(name="ip")
async def ip_command(ctx):
    embed = discord.Embed(
        title="📡 Información -  YT Open Source Bot",
        description="¡Aquí te dejamos la IP y la información acerca de nuestro servidor!",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🌐 Conexión",
        value="**IP:** ytopensourcebot.net\n**PUERTO:**Sigueme",
        inline=False
    )
    embed.add_field(
        name="📋 Información",
        value="El servidor es tanto para **JAVA** como para **BEDROCK**\n\nTambién, puedes entrar al servidor con cualquiera de estas versiones: **1.16 - 1.21**\n\nEl servidor es tanto **PREMIUM** como **NO PREMIUM**",
        inline=False
    )
    embed.set_footer(text="YT Open Source Bot ")
    await ctx.send(embed=embed)


@bot.event
async def on_member_join(member: discord.Member):
    """Evento cuando un miembro se une al servidor"""
    guild = member.guild
    
    if not bot.welcome_channel_id:
        return
    
    channel = guild.get_channel(bot.welcome_channel_id)
    if not channel:
        return
    
    member_count = guild.member_count
    
    embed = discord.Embed(
        title="¡Bienvenido a YT Open Source Bot!",
        description=(
            f"¡Hola! {member.mention}\n\n"
            "Bienvenido al servidor de YT Open Source Bot la mejor comunidad de Minecraft Java/Bedrock.\n\n"
            "**IP del servidor:** YT Open Source Bot\n\n"
            "**Nuestras redes:**\n"
            "Youtube: https://www.youtube.com/@carvajaal1\n"
            "¡Esperamos que disfrutes tu estadía!"
        ),
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Somos {member_count} miembros!")
    
    await channel.send(embed=embed)


@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print(f'ID: {bot.user.id}')
    print('------------------------')


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("No tienes permisos para usar este comando.", ephemeral=True)
    else:
        print(f"Error en comando: {error}")
        try:
            await interaction.response.send_message(f"Ocurrio un error: {str(error)}", ephemeral=True)
        except:
            pass



if __name__ == "__main__":
    TOKEN = "Tu token"
    bot.run(TOKEN)
