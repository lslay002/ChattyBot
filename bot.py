# ♪ C H A T T Y   B O T ♪
# Created for the r/PokemonMaxRaids discord server
# Authored by Ymir | Prince_of_Galar and Eldaste

# Setup
import discord
import asyncio
import os
import re
import postgres
import time
import settings
from discord.utils import get

# Establish settings and IO helpers
MODROLE = "Mods"
COMMANDCHNNUM = int(os.environ.get('COMMANDCHN'))
REPORTCHNNUM = int(os.environ.get('REPORTCHN'))
REMOVECHNNUM = int(os.environ.get('REMOVECHN'))
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

helptext = (
    ';get - What words are being watched for.\n'
    ';set - Add a word.\n'
    ';rm - Remove a word.\n'
    ';getr - What words are being autoremoved.\n'
    ';setr - Add a word to autoremove.\n'
    ';rmr - Remove a word from autoremove.\n'
    ';getm - What words are being automuted.\n'
    ';setm - Add a word to automute.\n'
    ';rmm - Remove a word from automute.\n'
    ';send <UserID> <Message> - Send a message to a user with Chatty\n'
    ';note <UserID> <Note (optional)> - With optional note: Make a note on the iven user. Without optional note: Retrieve notes on given user.\n'
    ';link <UserID> <Reddit Username> - Link a user to a Reddit username\n'
    ';echo <ChannelID> <Message> - Send a message to a channel with Chatty\n'
    ';perma <UserID> - Take a user off Chatty\'s auto-unban.\n'
    ';ban <UserID> <Reason (optional)> - Bans the given user with a message.\n'
    ';tempban <UserID> <Ban Length> <Reason (optional)> - Bans the given user with a message for the given amount of time. Ban length can be in hours or of the form "XwXdXh"\n'
    ';banstatus <UserID> - returns how long a tempbanned user will remain banned.\n'
    ';unban <UserID> - Unbans the given user.\n'
    ';clear <MessageID (optional)> - Marks each message above this or the given message as read, until  hitting a marked message, or a message not sent by me.'
)

warninglist = []
removelist = []
mutelist = []
watchlist = {}
exceptionlist = []
mention_dict = loadMentions()
keywordsFile = loadKeywords()
db = postgres.Postgres(url = os.environ.get('DATABASE_URL'))
db.run("CREATE TABLE IF NOT EXISTS forbidden (words text)")
db.run("CREATE TABLE IF NOT EXISTS vile (words text)")
db.run("CREATE TABLE IF NOT EXISTS automute (words text)")
db.run("CREATE TABLE IF NOT EXISTS tempbans (id bigint PRIMARY KEY, time int)")
db.run("CREATE TABLE IF NOT EXISTS usernotes (id bigint PRIMARY KEY, linkedact text, notes text)")
db.run("CREATE TABLE IF NOT EXISTS exempteds (id bigint)")

client = discord.Client()
mainServer = None
commandChn = None
reportChn = None
removeChn = None
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
composedremove = composeWarning(removelist)
composedmute = composeWarning(mutelist, False)

# Chennel spcific Commands, of the form of a dictonary with the IDs as keys, and the contents a list of lists,
# with the internal lists of the form [flags, RegEx, Message]
csCommands = loadSpecificChn()

# Helper method that takes a string of XhXdXw or a number in hours and converts to hours and a textual representation
timetokenregex = r'(?P<hours>[1234567890]+(?=h))|(?P<days>[1234567890]+(?=d))|(?P<weeks>[1234567890]+(?=w))|(?P<indicators>(?<=[1234567890])[hwd])|(?P<error>[\S])'
timetokenizer = re.compile(timetokenregex, re.I)
def timeReader(time = None):
    if time == None:
        return None
    if time == '':
        stringrep = None
        hourrep = 0
    elif str(time).isdigit():
        stringrep = None
        hourrep = int(time)
    else:
        stringrep = time
        hourrep = None
    if stringrep:
        temp = {'hours': 0, 'days': 0, 'weeks': 0}
        for token in timetokenizer.finditer(stringrep):
            typ = token.lastgroup
            val = token.group()
            if typ == 'hours':
                temp['hours'] += int(val)
            elif typ == 'weeks':
                temp['weeks'] += int(val)
            elif typ == 'days':
                temp['days'] += int(val)
            elif typ == 'error':
                raise RuntimeError('Unexpected formation of time string.')
        ttime = temp['hours'] + ((temp['days'] + (temp['weeks'] * 7)) * 24)
    else:
        temp = {'hours': 0, 'days': 0, 'weeks': 0}
        ttime = hourrep
        temp['hours'] = hourrep % 24
        hourrep //= 24
        temp['days'] = hourrep % 7
        temp['weeks'] = hourrep // 7
    tstring = ''
    if temp['weeks']:
        tstring += str(temp['weeks']) + ' Week'
        if temp['weeks'] != 1:
            tstring += 's'
    if temp['days']:
        if tstring != '':
            if temp['hours']:
                tstring += ', '
            else:
                tstring += ' and '
        tstring += str(temp['days']) + ' Day'
        if temp['days'] != 1:
            tstring += 's'
    if temp['hours']:
        if temp['days'] and temp['weeks']:
            tstring += ', and '
        elif temp['days'] or temp['weeks']:
            tstring += ' and '
        tstring += str(temp['hours']) + ' Hour'
        if temp['hours'] != 1:
            tstring += 's'
    if tstring == '':
        tstring = '0 Hours'
    return {'stringrep': tstring, 'hours': ttime}

# Helper method to analyze messages and ID length/emotes/pings
emojiregex = r'<a?:[^<>\s]+?:[1234567890]+>'
pingregex = r'<[@#]&?[1234567890]+>'
formattingregex = r'[`*_]|\|\||~~'
linkregex = r'[\S]+reddit\.com/r/pokemonmaxraids[\S]+'
emojichk = re.compile(emojiregex)
pingchk = re.compile(pingregex)
linkchk = re.compile(linkregex)
def analyzeAnnouncement(message):
    temp = message
    emoji = emojichk.findall(temp)
    temp = emojichk.sub('', temp)
    pings = pingchk.findall(temp)
    temp = pingchk.sub('', temp)
    links = linkchk.findall(temp)
    temp = linkchk.sub('', temp)
    temp, formnum = re.subn(formattingregex, '', temp)
    return {'length': len(temp) + len(emoji),
            'emoji': emoji,
            'pings': pings,
            'formattingamount': formnum,
            'lines': len(re.findall(r'\n', temp)) + 1,
            'words': len(temp.split()),
            'links': links,
            }

async def analyzePost(message, resultschn):
    ares = analyzeAnnouncement(message.content)
    if ares['length'] > 400 or ares['lines'] > 8:
        warnmess = discord.Embed(color = 0xcc8034)
        warnmess.add_field(name = 'Message Link', value = message.jump_url, inline = False)
    else:
        warnmess = discord.Embed(color = 0xcfc829)
    warnmess.title = 'Post Stats'
    warnmess.add_field(name = 'User', value = message.author.mention)
    warnmess.add_field(name = 'Channel', value = message.channel.name, inline = False)
    warnmess.add_field(name = 'Length', value = ares['length'])
    warnmess.add_field(name = 'Words', value = ares['words'])
    warnmess.add_field(name = 'Lines', value = ares['lines'])
    warnmess.add_field(name = 'Formatting Used', value = ares['formattingamount'])
    if len(ares['pings']) != 0:
        warnmess.add_field(name = 'Pings Used', value = '\n'.join(ares['pings']))
    if len(ares['emoji']) != 0:
        warnmess.add_field(name = 'Emoji Used', value = ' '.join(ares['emoji']), inline = False)
    if len(ares['links']) != 0:
        warnmess.add_field(name = 'Reddit Link', value = '\n'.join(ares['links']), inline = False)
    await resultschn.send(embed = warnmess)

# Functions to work with usernotes
def addNote(userID, modID, note):
    '''
        INSERT INTO usernotes SELECT %(id)s, '', '' WHERE NOT EXISTS(SELECT 1 FROM usernotes WHERE id = %(id)s)
        UPDATE usernotes SET notes = notes || '==X==' || %(mod)s || '////' || %(note)s WHERE id = %(id)s
        INSERT INTO usernotes VALUES (33, '', 11 || '////' || 'Hello')
    '''
    controlflow = db.one('SELECT notes FROM usernotes WHERE id = %(ids)s', ids = userID)
    
    if controlflow == None:
        db.run("INSERT INTO usernotes VALUES (%(ids)s, '', %(mod)s || '////' || %(notes)s || '////' || %(times)s)",
               ids = userID, mod = modID, notes = note, times = time.time())
    elif controlflow == '':
        db.run("UPDATE usernotes SET notes = %(mod)s || '////' || %(notes)s || '////' || %(times)s WHERE id = %(ids)s",
               ids = userID, mod = modID, notes = note, times = time.time())
    else:
        db.run("UPDATE usernotes SET notes = notes || '==X==' || %(mod)s || '////' || %(notes)s || '////' || %(times)s WHERE id = %(ids)s",
               ids = userID, mod = modID, notes = note, times = time.time())

def getNotes(userID): # Returns a list of mod/note/timestamp sequences
    data = db.one('SELECT notes FROM usernotes WHERE id = %(ids)s', ids = userID)

    if data == None or data == '':
        return []

    res = data.split('==X==')

    for x in range(len(res)):
        res[x] = res[x].split('////')

    return res

def linkAcct(userID, acctname): # Returns true if added, False if the name is invalid
    redditusernameregex = r'^(?:/[Uu]/)?([\w-]{3,})$'
    username = re.search(redditusernameregex, acctname)
    
    if username == None:
        return False
    
    acctname = username.group(1)
    
    controlflow = db.one('SELECT linkedact FROM usernotes WHERE id = %(ids)s', ids = userID)
    
    if controlflow == None:
        db.run("INSERT INTO usernotes VALUES (%(ids)s, %(notes)s, '')", ids = userID, notes = acctname)
    elif controlflow == '':
        db.run("UPDATE usernotes SET linkedact = %(notes)s WHERE id = %(ids)s", ids = userID, notes = acctname)
    else:
        db.run("UPDATE usernotes SET linkedact = linkedact || ' ' || %(notes)s WHERE id = %(ids)s", ids = userID, notes = acctname)

    return True

def getLinkedAccts(userID): # Returns a list associated usernames
    data = db.one('SELECT linkedact FROM usernotes WHERE id = %(ids)s', ids = userID)

    if data == None:
        return []

    res = data.split()

    return res

async def sendNotes(userID, channel):
    linked = getLinkedAccts(userID)
    notes = getNotes(userID)

    colors = [
            0x48db9c,
            0xa3f7d3,
            0x88d1b1,
            0x81c7a8,
            0x74b397,
            0x659c83,
            0x54806c,
            0x476e5c,
            0x375748,
            0x2a4237,
        ]

    warnmess = discord.Embed(color = colors[len(notes)] if len(notes) < len(colors) else colors[-1])
    warnmess.title = 'Notes for User ID %s' % str(userID)

    temp = client.get_user(int(userID))
    if temp != None:
        warnmess.add_field(name = 'Username', value = temp.name, inline = False)

    if linked != []:
        warnmess.add_field(name = 'Reddit' if len(linked) == 1 else 'Reddits', value = ', '.join(linked), inline = False)

    if userID in exceptionlist:
        warnmess.add_field(name = 'Exempted', value = 'from regular filters', inline = False)

    contents = ''
    remainder = ''
    for tup in notes:
        mod = client.get_user(int(tup[0]))
        mod = mod.name if mod != None else '<@%s>' % str(tup[0])
        timestamp = time.gmtime(float(tup[2]))
        timestamp = '%d/%d/%d' % (timestamp.tm_mon, timestamp.tm_mday, timestamp.tm_year)
        contents += "**Note by %s - %s**\n%s\n\n" % (mod, timestamp, tup[1])

    contents = contents[:-2]

    if len(contents) > 1000:
        remainder = contents[1000:]
        contents = contents[:1000]

    if contents != '':
        warnmess.add_field(name = 'Notes', value = contents, inline = False)

    await channel.send(embed = warnmess)

    while remainder != '':
        warnmess = discord.Embed(color = colors[len(notes)] if len(notes) < len(colors) else colors[-1])
        warnmess.title = 'Notes for User ID %s: Cont...' % str(userID)

        if len(remainder) > 1000:
            contents = remainder[:1000]
            remainder = remainder[1000:]
        else:
            contents = remainder
            remainder = ''

        warnmess.add_field(name = 'Notes', value = contents, inline = False)

        await channel.send(embed = warnmess)

# Helper method to ban users and send messages.
async def banUser(user, guild, time = -1, reason = None, message =  None):
    bannote = 'Banned'
    
    if message != None:
        try:
            targetchn = user.dm_channel
            if targetchn == None:
                await user.create_dm()
                targetchn = user.dm_channel
            await targetchn.send(message)
        except:
            await logChn.send("Unable to send message to user " + str(user))
        
    if reason != None:
        await guild.ban(user, reason = reason, delete_message_days = 0)
    else:
        await guild.ban(user, delete_message_days = 0)

    if time != -1:
        db.run("INSERT INTO tempbans VALUES (%(newid)s, %(duration)s)", newid = user.id, duration = time)
        bannote = 'Tempbanned'

    if reason != None:
        bannote += " - " + reason
    
    warnmess = discord.Embed(color = 0x810e0e)
    warnmess.title = 'User Banned'
    warnmess.add_field(name = 'User', value = user.mention)
    warnmess.add_field(name = 'ID', value = user.id)
    if time != -1:
        warnmess.add_field(name = 'Duration', value = timeReader(time)['stringrep'])
    if reason != None:
        warnmess.add_field(name = 'Reason', value = reason, inline = False)
    await logChn.send(embed = warnmess)

    addNote(user.id, client.user.id, bannote)

# Unbanning functions, seperated to allow code reuse.
async def unbanUser(userid):
    try:
        hold = await client.fetch_user(userid)
        await mainServer.unban(hold)
        warnmess = discord.Embed(color = 0x4044df)
        warnmess.title = 'User Unbanned'
        warnmess.add_field(name = 'User', value = hold)
        warnmess.add_field(name = 'ID', value = userid)
        await logChn.send(embed = warnmess)
        db.run("DELETE FROM tempbans WHERE id=(%(old)s)", old = userid)
    except:
        await logChn.send('Something went wrong unbanning User ID: ' + str(userid))
    

# Event loop to handle unbanning users that have been tempbanned, also clears the watchlist
async def unbanLoop():
    global watchlist
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(30) # timers mesured in hours to go
        print('Hour Ping')
        watchlist = {}
        db.run("UPDATE tempbans SET time = time - 1")
        unbanlist = db.all('SELECT id FROM tempbans WHERE time <= 0')
        for unbanid in unbanlist:
            await unbanUser(unbanid)

# Monitor all messages for danger words and report them to the mods
# Also reply to messages with certian mentions in them
@client.event
async def on_message(msg):
    # Handle commands
    global warninglist, composedwarning, watchlist, removelist, composedremove, mutelist, composedmute, exceptionlist

    if not msg.author.bot and msg.channel.type == discord.ChannelType.private:
        attach = ''
        warnmess = discord.Embed()
        warnmess.title = 'User Report'
        warnmess.add_field(name = 'User', value = msg.author.mention)
        warnmess.add_field(name = 'ID', value = msg.author.id)
        if msg.content != '':
            if len(msg.content) < 1000:
                warnmess.add_field(name = 'Report Contents', value = msg.content, inline = False)
            else:
                warnmess.add_field(name = 'Report Contents', value = msg.content[:1000], inline = False)
        attach = '\n'.join(map(lambda x: x.url, msg.attachments))
        if attach != '':
            warnmess.add_field(name = 'Attachments', value = attach, inline = False)
        if len(msg.content) < 1000:
            warnmess.set_footer(text = 'To reply to a user with a message from Chatty, use ;send <UserID> <Message>')
        else:
            warnmess.set_footer(text = 'Message continued...')
        await reportChn.send(embed = warnmess)
        if len(msg.content) >= 1000:
            warnmess = discord.Embed()
            warnmess.title = 'User Report - Continued'
            warnmess.add_field(name = 'User', value = msg.author.mention)
            warnmess.add_field(name = 'ID', value = msg.author.id)
            warnmess.add_field(name = 'Report Contents', value = msg.content[1000:], inline = False)
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
            elif splitmes[0] == ';getr':
                await commandChn.send(', '.join(map(lambda x: '`' + x + '`', removelist)))
            elif splitmes[0] == ';setr':
                if len(splitmes) == 1:
                    await commandChn.send('What word or regular expression would you like to be removed?')
                    return
                removelist.append(splitmes[1])
                db.run("INSERT INTO vile VALUES (%(new)s)", new = splitmes[1])
                composedremove = composeWarning(removelist)
                await commandChn.send('Word added.')
            elif splitmes[0] == ';rmr':
                if len(splitmes) == 1:
                    await commandChn.send('What word or regular expression would you like to not be removed?')
                    return
                removelist.remove(splitmes[1])
                db.run("DELETE FROM vile WHERE words=(%(old)s)", old = splitmes[1])
                composedremove = composeWarning(removelist)
                await commandChn.send('Word removed.')
            elif splitmes[0] == ';getm':
                await commandChn.send(', '.join(map(lambda x: '`' + x + '`', mutelist)))
            elif splitmes[0] == ';setm':
                if len(splitmes) == 1:
                    await commandChn.send('What word or regular expression would you like to be an automute?')
                    return
                mutelist.append(splitmes[1])
                db.run("INSERT INTO automute VALUES (%(new)s)", new = splitmes[1])
                composedmute = composeWarning(mutelist, False)
                await commandChn.send('Word added.')
            elif splitmes[0] == ';rmm':
                if len(splitmes) == 1:
                    await commandChn.send('What word or regular expression would you like to not be an automute?')
                    return
                mutelist.remove(splitmes[1])
                db.run("DELETE FROM automute WHERE words=(%(old)s)", old = splitmes[1])
                composedmute = composeWarning(mutelist, False)
                await commandChn.send('Word removed.')
                
            if splitmes[0] == ';getex':
                await commandChn.send(', '.join(map(lambda x: '<@' + str(x) + '>', exceptionlist)))
            elif splitmes[0] == ';setex':
                if len(splitmes) == 1:
                    await commandChn.send('What user would you like to exempt?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID.')
                    return
                exceptionlist.append(int(splitmes[1]))
                db.run("INSERT INTO exempteds VALUES (%(new)s)", new = splitmes[1])
                await commandChn.send('User exempted.')
            elif splitmes[0] == ';rmex':
                if len(splitmes) == 1:
                    await commandChn.send('What user would you like to remove from the exemption list?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID.')
                    return
                exceptionlist.remove(int(splitmes[1]))
                db.run("DELETE FROM exempteds WHERE id=(%(old)s)", old = splitmes[1])
                await commandChn.send('User removed.')
                
            elif splitmes[0] == ';perma':
                if len(splitmes) == 1:
                    await commandChn.send('What user would you no longer like to come back?')
                    return
                db.run("DELETE FROM tempbans WHERE id=(%(old)s)", old = splitmes[1])
                await commandChn.send('User removed.')
            elif splitmes[0] == ';unban':
                if len(splitmes) == 1:
                    await commandChn.send('What user would you like to unban?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID as a target of who to unaban.')
                    return
                await unbanUser(int(splitmes[1]))
            elif splitmes[0] == ';banstatus':
                if len(splitmes) == 1:
                    await commandChn.send('What user would you like to check?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID as a target of who to check.')
                    return
                time = timeReader(db.one("SELECT time FROM tempbans WHERE id=(%(old)s)", old = splitmes[1]))
                if not time:
                    time = {'stringrep': 'This user is not tempbanned.'}
                await msg.channel.send(time['stringrep'])
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
            elif splitmes[0] == ';note':
                if len(splitmes) == 1:
                    await msg.channel.send('Which user?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID.')
                    return
                if len(splitmes) == 2:
                    await sendNotes(splitmes[1], msg.channel)
                    return
                addNote(splitmes[1], msg.author.id, ' '.join(splitmes[2:]))
                'Should be no issue'
                await msg.channel.send('Note Added.')
            elif splitmes[0] == ';link':
                if len(splitmes) == 1:
                    await msg.channel.send('Which user?')
                    return
                if len(splitmes) == 2:
                    await msg.channel.send('Which Reddit account?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID.')
                    return
                if linkAcct(splitmes[1], splitmes[2]):
                        await msg.channel.send('Account Linked.')
                else:
                        await msg.channel.send('Invalid Reddit Username.')
            elif splitmes[0] == ';echo':
                if len(splitmes) == 1:
                    await msg.channel.send('Where would you like to send a message to?')
                    return
                if len(splitmes) == 2:
                    await msg.channel.send('What message would you like to send?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a ChannelID as a target of where to send to.')
                    return
                target = client.get_channel(int(splitmes[1]))
                if target == None:
                    await msg.channel.send('Channel not found.')
                    return
                await target.send(' '.join(splitmes[2:]))
                await msg.channel.send('Message sent.')
            elif splitmes[0] == ';ban':
                if len(splitmes) == 1:
                    await msg.channel.send('Who would you like to ban?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID as a target of who to ban.')
                    return
                target = client.get_user(int(splitmes[1]))
                if target != None:
                    if len(splitmes) == 2:
                        reason = None
                        bantext = "You have been banned from " + settings.guildName + ". " + settings.appealMes
                    else:
                        reason = ' '.join(splitmes[2:])
                        bantext = "You have been banned from " + settings.guildName + " for the following reasons:\n`" + reason + "`\n" + settings.appealMes
                else:
                    target = await client.fetch_user(int(splitmes[1]))
                    if len(splitmes) == 2:
                        reason = None
                        bantext = None
                    else:
                        reason = ' '.join(splitmes[2:])
                        bantext = None
                if target == None:
                    await msg.channel.send('User not found.')
                    return
                await banUser(target, msg.guild, -1, reason, bantext)
            elif splitmes[0] == ';sban':
                if len(splitmes) == 1:
                    await msg.channel.send('Who would you like to ban?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID as a target of who to ban.')
                    return
                target = client.get_user(int(splitmes[1]))
                if target == None:
                    target = await client.fetch_user(int(splitmes[1]))
                if len(splitmes) == 2:
                    reason = None
                else:
                    reason = ' '.join(splitmes[2:])
                if target == None:
                    await msg.channel.send('User not found.')
                    return
                await banUser(target, msg.guild, -1, reason)
            elif splitmes[0] == ';tempban':
                if len(splitmes) == 1:
                    await msg.channel.send('Who would you like to ban?')
                    return
                if len(splitmes) == 2:
                    await msg.channel.send('How long do you want the ban to be?')
                    return
                if not str(splitmes[1]).isdigit():
                    await msg.channel.send('Please use a UserID as a target of who to ban.')
                    return
                try:
                    duration = timeReader(splitmes[2])
                except:
                    await msg.channel.send('Malformed duration. Please use a time of the form XhXdXw or use time in hours.')
                    return
                target = client.get_user(int(splitmes[1]))
                if target != None:
                    if len(splitmes) == 3:
                        reason = None
                        bantext = "You have been banned from " + settings.guildName + " for " + duration['stringrep'] + ". " + settings.appealMes
                    else:
                        reason = ' '.join(splitmes[3:])
                        bantext = "You have been banned from " + settings.guildName + " for " + duration['stringrep'] + " for the following reasons:\n`" + reason + "`\n" + settings.appealMes
                else:
                    target = await client.fetch_user(int(splitmes[1]))
                    if len(splitmes) == 3:
                        reason = None
                        bantext = None
                    else:
                        reason = ' '.join(splitmes[3:])
                        bantext = None
                if target == None:
                    await msg.channel.send('User not found.')
                    return
                await banUser(target, msg.guild, duration['hours'], reason, bantext)
            elif splitmes[0] == ';clear':
                if len(splitmes) == 1:
                    current = await msg.channel.history(limit = 1, before = msg).next()
                else:
                    if not str(splitmes[1]).isdigit():
                        await msg.channel.send('Please use a MessageID as an argument.')
                        return
                    else:
                        current = await msg.channel.fetch_message(int(splitmes[1]))
                rxnimage = client.get_emoji(settings.reactemote)
                while current.author == client.user and len(current.reactions) == 0:
                    await current.add_reaction(rxnimage)
                    current = await msg.channel.history(limit = 1, before = current).next()
            elif splitmes[0] == ';locate':
                if len(splitmes) == 1:
                    await msg.channel.send('Who would you like to search for?')
                    return
                composedRE = ' '.join(splitmes[1:])
                nuum = composedRE.isdigit()
                found = 0
                startmes = 'Searching for users '
                if nuum:
                    startmes = startmes + 'and discriminators '
                startmes = startmes + 'that match Regex: ' + composedRE
                await msg.channel.send(startmes)
                for usr in msg.guild.members:
                    if nuum:
                        if re.search(composedRE, usr.discriminator):
                            await msg.channel.send('User Discriminator Matched: ' + usr.mention)
                            found += 1
                            continue
                    if re.search(composedRE, usr.name):
                        await msg.channel.send('UserMatched: ' + usr.mention)
                        found += 1
                        continue
                    if re.search(composedRE, usr.nick):
                        await msg.channel.send('UserMatched: ' + usr.mention)
                        found += 1
                        continue
                if found == 0:
                    msg.channel.send('No matching users found.')
                else:
                    msg.channel.send(str(found) + ' users found.')
            elif splitmes[0] == ';help':
                await commandChn.send(helptext)
            #else:
            #    await commandChn.send('What do I do with this?')
        return

    # Auto note things in the LogChn that mention users that aren't bot generated
    if not msg.author.bot and msg.channel.id == LOGCHNNUM:
        for mention in msg.mentions:
            addNote(mention.id, msg.author.id, msg.content)
        
    # If from a bot or the mods or in the Muted Channel, ignore
    if msg.author.bot or get(msg.author.roles, name = MODROLE) or msg.channel.id == settings.autoCallChn:
        return

    # Remove vile words
    dangerwords = filter(composedremove.match, msg.content.split())

    cdw = ', '.join(map(str, dangerwords))
    if cdw != '':
        if composedmute.search(cdw):
            temp = msg.author
        else:
            temp = None
        warnmess = discord.Embed()
        warnmess.title = 'Vile Content Removal Report'
        warnmess.add_field(name = 'User', value = msg.author.mention)
        warnmess.add_field(name = 'ID', value = msg.author.id)
        warnmess.add_field(name = 'Channel', value = msg.channel.name, inline = False)
        #warnmess.add_field(name = 'Words', value = cdw, inline = True)
        warnmess.add_field(name = 'Message', value = msg.content, inline = False)
        await msg.delete()
        await removeChn.send(embed = warnmess)
        if temp:
            await temp.add_roles(mainServer.get_role(settings.autoCallRole))
            tmchn = client.get_channel(settings.autoCallChn)
            await tmchn.send('Hello, {}!\nYou are currently muted. Please take a moment to review our <#{}>. <@&{}> will be with you as soon as possible.'.format(temp.mention, settings.ruleChn, settings.modRole))
        return

    # Check user messages for keywords in the trading channel
    if msg.channel.name == 'trading':
        for keywords in keywordsFile:
            if keywords in msg.content.lower():
                warnmess = discord.Embed()
                warnmess.title = 'Removal Report'
                warnmess.add_field(name = 'User', value = msg.author.mention)
                warnmess.add_field(name = 'ID', value = msg.author.id)
                warnmess.add_field(name = 'Channel', value = 'Trading', inline = False)
                #warnmess.add_field(name = 'Word', value = keywords, inline = True)
                warnmess.add_field(name = 'Message', value = msg.content, inline = False)
                await removeChn.send(embed = warnmess)
                if msg.author.id in watchlist:
                    await banUser(msg.author, msg.guild, 24, 'Multiple trade violations', "You've been banned for one day due to repeatedly trying to trade prohibited Pokemon. If you believe this was a mistake, you can appeal your ban here: https://www.reddit.com/message/compose?to=%2Fr%2Fpokemonmaxraids")
                else:
                    watchlist[msg.author.id] = True
                    await msg.channel.send("Hello, {}! ♪".format(msg.author.mention) + '\nReminder that trades for shinies, events, legendaries, and Dittos are not allowed. Please reread the rules in the channel pins!')
                await msg.delete()
                return

    # Analyze the message for warning words, notify mods if any appear
    if msg.author.id not in exceptionlist:
        dangerwords = filter(composedwarning.match, msg.content.split())

        cdw = ', '.join(map(str, dangerwords))
        if cdw != '':
            warnmess = discord.Embed()
            warnmess.title = 'Warning Report'
            warnmess.add_field(name = 'User', value = msg.author.mention)
            warnmess.add_field(name = 'Words Used', value = cdw)
            warnmess.add_field(name = 'Message Link', value = msg.jump_url, inline = False)
            if settings.warningPreviewLen != 0:
                preview = msg.content if len(msg.content) < settings.warningPreviewLen else msg.content[:settings.warningPreviewLen] + '...'
                warnmess.add_field(name = 'Preview', value = preview)
            await commandChn.send(embed = warnmess)

    # Check mentions of a message and send messages when needed
    for mention in msg.role_mentions:
        val = str(mention.id)
        if val in mention_dict:
            await msg.channel.send('\n'.join(map(str, mention_dict[val])))

    ## Do things involving the announcements
    #if msg.channel.id == settings.announcechn:
    #    await analyzePost(msg, commandChn)

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
                        warnmess.add_field(name = 'User', value = msg.author.mention)
                        warnmess.add_field(name = 'Words Used', value = chkwords)
                        warnmess.add_field(name = 'Message Link', value = msg.jump_url, inline = False)
                        if settings.warningPreviewLen != 0:
                            preview = msg.content if len(msg.content) < settings.warningPreviewLen else msg.content[:settings.warningPreviewLen] + '...'
                            warnmess.add_field(name = 'Preview', value = preview)

                        if flag == 'l':
                            await logChn.send(embed = warnmess)
                        elif flag == 'c':
                            await commandChn.send(embed = warnmess)
                        else:
                            await reportChn.send(embed = warnmess)
                    elif flag == 'r':
                        await msg.channel.send(command[2])
                    elif flag == 'f':
                        await msg.channel.send(command[2].format(msg.author.mention))
                    elif flag == 'd':
                        warnmess = discord.Embed()
                        warnmess.title = 'Removal Report'
                        warnmess.add_field(name = 'User', value = msg.author.mention)
                        warnmess.add_field(name = 'ID', value = msg.author.id)
                        warnmess.add_field(name = 'Channel', value = msg.channel.name, inline = False)
                        #warnmess.add_field(name = 'Words', value = chkwords, inline = True)
                        warnmess.add_field(name = 'Message', value = msg.content, inline = False)
                        await removeChn.send(embed = warnmess)
                        dele = True
                if dele:
                    await msg.delete()
                    return

## Watces edits for if the message breaks removal/other filters
#@client.event
#async def on_raw_message_edit(payload):

# When bot is ready, open the command channel
@client.event
async def on_ready():
    global commandChn, warninglist, composedwarning, reportChn, logChn, mainServer, composedremove, removelist
    global mutelist, composedmute, removeChn, exceptionlist 
    commandChn = client.get_channel(COMMANDCHNNUM)
    reportChn = client.get_channel(REPORTCHNNUM)
    logChn = client.get_channel(LOGCHNNUM)
    removeChn = client.get_channel(REMOVECHNNUM)
    mainServer = commandChn.guild
    warninglist = db.all('SELECT words FROM forbidden')
    composedwarning = composeWarning(warninglist)
    removelist = db.all('SELECT words FROM vile')
    composedremove = composeWarning(removelist)
    mutelist = db.all('SELECT words FROM automute')
    composedmute = composeWarning(mutelist, False)
    exceptionlist = db.all('SELECT id FROM exempteds')
    print('Logged in as ' + client.user.name)

# runs the app
if __name__ == '__main__':
    client.loop.create_task(unbanLoop())
    client.run(os.environ.get('TOKEN'))

