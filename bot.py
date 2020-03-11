# ♪ C H A T T Y   B O T ♪
# Created for the r/PokemonMaxRaids discord server
# Authored by Ymir | Prince_of_Galar and Eldaste

# Setup
import discord
import asyncio
import os
import re
import postgres
from discord.utils import get

# Establish settings and IO helpers
MODROLE = "Mods"
COMMANDCHNNUM = int(os.environ.get('COMMANDCHN'))
REPORTCHNNUM = int(os.environ.get('REPORTCHN'))
LOGCHNNUM = int(os.environ.get('LOGCHN'))

def loadMentions():
    tmpm = {}
    with open('./data/mentioninfo.txt') as f:
        for line in f:
            tt = line.split('|')
            key, rest = tt[0], tt[1:]
            tmpm[key] = rest
    return tmpm

def loadKeywords():
    tmpm = []
    # Open the keywords text file
    with open('./data/keywords.txt','r') as f:
        tempm = f.read().split(' | ')
    return tempm

warninglist = []
watchlist = {}
mention_dict = loadMentions()
keywordsFile = loadKeywords()
db = postgres.Postgres(url = os.environ.get('DATABASE_URL'))
db.run("CREATE TABLE IF NOT EXISTS forbidden (words text)")
db.run("CREATE TABLE IF NOT EXISTS tempbans (id bigint PRIMARY KEY, time int)")

client = discord.Client()
mainServer = None
commandChn = None
reportChn = None
logChn = None

# Helper function to help create the warnings
def composeWarning(values, singleword = True):
    temp = '|'.join(map(str, values))
    temp = r'\W*(' + temp + r')\W*'
    if singleword:
        temp = temp + r'\Z'
    return re.compile(temp, re.I)

# Load ChannelSpecific Warning File
def loadSpecificChn():
    csw = {}
    with open('./data/csw.txt') as f:
        for line in f:
            ll = line.split(r'=|=')
            if len(ll) < 3:
                continue
            tempholder = [ll[1], composeWarning(ll[2].split(r'||'))]
            if len(ll) > 3:
                tempholder.append(ll[3])
            else:
                tempholder.append('No message set.')
            for x in ll[0].split(r'||'):
                if x not in csw:
                    csw[x] = []
                csw[x].append(tempholder)
    return csw

# Composed warning (a regex object)
composedwarning = composeWarning(warninglist)

# Chennel spcific Commands, of the form of a dictonary with the IDs as keys, and the contents a list of lists,
# with the internal lists of the form [flags, RegEx, Message]
csCommands = loadSpecificChn()

# Helper method to ban users and send messages.
async def banUser(user, guild, time = -1, reason = None, message =  None):
    if message != None:
        targetchn = user.dm_channel
        if targetchn == None:
            await user.create_dm()
            targetchn = user.dm_channel
        await targetchn.send(message)
        
    if reason != None:
        await guild.ban(user, reason = reason, delete_message_days = 0)
    else:
        await guild.ban(user, delete_message_days = 0)

    if time != -1:
        db.run("INSERT INTO tempbans VALUES (%(newid)s, %(duration)s)", newid = user.id, duration = time)
    
    warnmess = discord.Embed()
    warnmess.title = 'User Banned'
    warnmess.add_field(name = 'User', value = user)
    warnmess.add_field(name = 'ID', value = user.id)
    if reason != None:
        warnmess.add_field(name = 'Reason', value = reason, inline = False)
    await logChn.send(embed = warnmess)

# Event loop to handle unbanning users that have been tempbanned, also clears the watchlist
async def unbanLoop():
    global watchlist
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(360) # timers mesured in hours to go
        watchlist = {}
        db.run("UPDATE tempbans SET time = time - 1")
        unbanlist = db.all('SELECT id FROM tempbans WHERE time <= 0')
        for unbanid in unbanlist:
            try:
                hold = await client.fetch_user(unbanid)
                await mainServer.unban(hold)
                warnmess = discord.Embed()
                warnmess.title = 'User Unbanned'
                warnmess.add_field(name = 'User', value = hold)
                warnmess.add_field(name = 'ID', value = unbanid)
                await logChn.send(embed = warnmess)
            except:
                await logChn.send('Something went wrong unbanning User ID: ' + str(unbanid))
            db.run("DELETE FROM tempbans WHERE id = %(uid)s", uid = unbanid)

# Monitor all messages for danger words and report them to the mods
# Also reply to messages with certian mentions in them
@client.event
async def on_message(msg):
    # Handle commands
    global warninglist, composedwarning, watchlist

    if not msg.author.bot and msg.channel.type == discord.ChannelType.private:
        warnmess = discord.Embed()
        warnmess.title = 'User Report'
        warnmess.add_field(name = 'User', value = msg.author)
        warnmess.add_field(name = 'ID', value = msg.author.id)
        warnmess.add_field(name = 'Report Contents', value = msg.content, inline = False)
        warnmess.set_footer(text = 'To reply to a user with a message from Chatty, use ;send <UserID> <Message>')
        await reportChn.send(embed = warnmess)
        return
                
    if not msg.author.bot and (msg.channel.id == COMMANDCHNNUM or (msg.channel.id == REPORTCHNNUM and msg.content.startswith(';send'))):
        if get(msg.author.roles, name = MODROLE):
            #print('Command Recieved')
            splitmes = msg.content.split()
            
            if len(splitmes) == 0:
                return
            
            if splitmes[0] == ';get':
                await commandChn.send(', '.join(map(lambda x: '`' + x + '`', warninglist)))
            elif splitmes[0] == ';set':
                if len(splitmes) == 1:
                    await commandChn.send('What word or regular expression would you like to be notified of?')
                    return
                warninglist.append(splitmes[1])
                db.run("INSERT INTO forbidden VALUES (%(new)s)", new = splitmes[1])
                composedwarning = composeWarning(warninglist)
                await commandChn.send('Word added.')
            elif splitmes[0] == ';rm':
                if len(splitmes) == 1:
                    await commandChn.send('What word or regular expression would you like to not be notified of?')
                    return
                warninglist.remove(splitmes[1])
                db.run("DELETE FROM forbidden WHERE words=(%(old)s)", old = splitmes[1])
                composedwarning = composeWarning(warninglist)
                await commandChn.send('Word removed.')
            elif splitmes[0] == ';perma':
                if len(splitmes) == 1:
                    await commandChn.send('What user would you no longer like to come back?')
                    return
                db.run("DELETE FROM tempbans WHERE id=(%(old)s)", old = splitmes[1])
                await commandChn.send('User removed.')
            elif splitmes[0] == ';send':
                if len(splitmes) == 1:
                    await msg.channel.send('Who would you like to send a message to?')
                    return
                if len(splitmes) == 2:
                    await msg.channel.send('What message would you like to send?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID as a target of who to send to.')
                    return
                target = client.get_user(int(splitmes[1]))
                if target == None:
                    await msg.channel.send('User not found.')
                    return
                targetchn = target.dm_channel
                if targetchn == None:
                    await target.create_dm()
                    targetchn = target.dm_channel
                await targetchn.send(' '.join(splitmes[2:]))
                await msg.channel.send('Message sent.')
            elif splitmes[0] == ';help':
                await commandChn.send(';get - What words are being watched for.\n;set - Add a word.\n;rm - Remove a word.\n;send <UserID> <Message> - Send a message to a user with Chatty\n;perma <UserID> - Take a user off Chatty\'s auto-unban.')
            #else:
            #    await commandChn.send('What do I do with this?')
        return
        
    # If from a bot or the mods, ignore
    if msg.author.bot or get(msg.author.roles, name = MODROLE):
        return

    # Check user messages for keywords in the trading channel
    if msg.channel.name == 'trading':
        for keywords in keywordsFile:
            if keywords in msg.content.lower():
                warnmess = discord.Embed()
                warnmess.title = 'Removal Report'
                warnmess.add_field(name = 'User', value = msg.author)
                warnmess.add_field(name = 'ID', value = msg.author.id)
                warnmess.add_field(name = 'Channel', value = 'Trading', inline = False)
                warnmess.add_field(name = 'Message', value = msg.content, inline = False)
                await logChn.send(embed = warnmess)
                if msg.author.id in watchlist:
                    await banUser(msg.author, msg.guild, 24, 'Multiple trade violations', "You've been banned for one day due to repeatedly trying to trade prohibited Pokemon. If you believe this was a mistake, you can appeal your ban here: https://www.reddit.com/message/compose?to=%2Fr%2Fpokemonmaxraids")
                else:
                    watchlist[msg.author.id] = True
                    await msg.channel.send("Hello, {}! ♪".format(msg.author.mention) + '\nReminder that trades for shinies, events, legendaries, and Dittos are not allowed. Please reread the rules in the channel pins!')
                await msg.delete()
                return

    # Analyze the message for warning words, notify mods if any appear
    dangerwords = filter(composedwarning.match, msg.content.split())

    cdw = ', '.join(map(str, dangerwords))
    if cdw != '':
        warnmess = discord.Embed()
        warnmess.title = 'Warning Report'
        warnmess.add_field(name = 'User', value = msg.author)
        warnmess.add_field(name = 'Words Used', value = cdw)
        warnmess.add_field(name = 'Message Link', value = msg.jump_url, inline = False)
        await commandChn.send(embed = warnmess)

    # Check mentions of a message and send messages when needed
    for mention in msg.role_mentions:
        val = str(mention.id)
        if val in mention_dict:
            await msg.channel.send('\n'.join(map(str, mention_dict[val])))

    # Handle Channel Specific catchlists
    if str(msg.channel.id) in csCommands:
        for command in csCommands[str(msg.channel.id)]:
            chkwords = ', '.join(filter(command[1].match, msg.content.split()))
                        
            if chkwords != '':
                dele = False

                for flag in command[0]:
                    if flag in 'lct':
                        warnmess = discord.Embed()
                        warnmess.title = 'Channel Specific Warning Report'
                        warnmess.add_field(name = 'User', value = msg.author)
                        warnmess.add_field(name = 'Words Used', value = chkwords)
                        warnmess.add_field(name = 'Message Link', value = msg.jump_url, inline = False)

                        if flag == 'l':
                            await logChn.send(embed = warnmess)
                        elif flag == 'c':
                            await commandChn.send(embed = warnmess)
                        else:
                            await reportChn.send(embed = warnmess)
                    elif flag == 'r':
                        await msg.channel.send(command[2])
                    elif flag == 'd':
                        warnmess = discord.Embed()
                        warnmess.title = 'Removal Report'
                        warnmess.add_field(name = 'User', value = msg.author)
                        warnmess.add_field(name = 'ID', value = msg.author.id)
                        warnmess.add_field(name = 'Channel', value = msg.channel.name, inline = False)
                        warnmess.add_field(name = 'Message', value = msg.content, inline = False)
                        await logChn.send(embed = warnmess)
                        dele = True
                if dele:
                    await msg.delete()
                    return

# If a user with the Max Host role adds a :pushpin: (📌) reaction to a message, the message will be pinned
@client.event
async def on_raw_reaction_add(payload):
    guild = await client.fetch_guild(guild_id = payload.guild_id)
    member = await guild.fetch_member(member_id = payload.user_id)
    channel = client.get_channel(id = payload.channel_id)
    if payload.emoji.name == "📌" and get(member.roles, name = "Max Host") and channel.name != 'trading':
        message = await channel.fetch_message(id = payload.message_id)
        await message.pin()

# If a user with the Max Host role removes a :pushpin: (📌) reaction from the message, the message will be unpinned
@client.event
async def on_raw_reaction_remove(payload):
    guild = await client.fetch_guild(guild_id = payload.guild_id)
    member = await guild.fetch_member(member_id = payload.user_id)
    channel = client.get_channel(id = payload.channel_id)
    if payload.emoji.name == "📌" and get(member.roles, name = "Max Host") and channel.name != 'trading':
        message = await channel.fetch_message(id = payload.message_id)
        await message.unpin()

# When bot is ready, open the command channel
@client.event
async def on_ready():
    global commandChn, warninglist, composedwarning, reportChn, logChn, mainServer
    commandChn = client.get_channel(COMMANDCHNNUM)
    reportChn = client.get_channel(REPORTCHNNUM)
    logChn = client.get_channel(LOGCHNNUM)
    mainServer = commandChn.guild
    warninglist = db.all('SELECT words FROM forbidden')
    composedwarning = composeWarning(warninglist)
    print('Logged in as ' + client.user.name)

# runs the app
if __name__ == '__main__':
    client.loop.create_task(unbanLoop())
    client.run(os.environ.get('TOKEN'))

