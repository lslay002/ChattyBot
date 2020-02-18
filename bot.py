#Chatty Bot
#Created for the r/PokemonMaxRaids discord server
#Authored by Ymir | Prince_of_Galar and Eldaste

#setup
import discord
import asyncio
import os
import re
from discord.utils import get

# Establish settings and IO helpers
MODROLE = "Mods"
COMMANDCHNNUM = 679171643444035594

def loadMentions():
    tmpm = {}
    with open('./data/mentioninfo.txt') as f:
        for line in f:
            tt = line.split('|')
            key, rest = tt[0], tt[1:]
            tmpm[key] = rest
    return tmpm

warninglist = ['test', r'part.*']
mention_dict = loadMentions()

client = discord.Client()
commandChn = None

#Helper function to help create the warnings
def composeWarning(values):
    temp = '|'.join(map(str, values))
    temp = '(' + temp + r')\Z'
    return re.compile(temp)

#Composed awarning (a regex object)
composedwarning = composeWarning(warninglist)

#Monitor all messages for danger words and report them to the mods
#Also reply to messages with certian mentions in them
@client.event
async def on_message(msg):
    # Handle commands
    if not msg.author.bot and msg.channel.id == COMMANDCHNNUM:
        if get(msg.author.roles, name = MODROLE):
            print('Command Recieved')
            commandChn.send('What do I do with this?')
        return
        
    # If from a bot or the mods, ignore
    if msg.author.bot or get(msg.author.roles, name = MODROLE):
        return

    # Analyze the message for warning words, notify mods if any appear
    dangerwords = filter(composedwarning.match, msg.content.split())

    cdw = ', '.join(map(str, dangerwords))
    if cdw != '':
        warnmess = discord.Embed()
        warnmess.title = 'Warning Report'
        warnmess.add_field(name = 'User', value = msg.author)
        warnmess.add_field(name = 'Words Used', value = cdw)
        warnmess.add_field(name = 'Message Link', value = msg.jump_url)
        commandChn.send(embed = warnmess)

    # Check mentions of a message and send messages when needed
    for mention in msg.role_mentions:
        if mention.id in mention_dict:
            msg.channel.send(mention_dict[mention.id])

#If a user with the Max Host role adds a :pushpin: (📌) reaction to a message, the message will be pinned
@client.event
async def on_reaction_add(reaction, user):
    if get(user.roles, name = "Max Host") and reaction.emoji == '📌':
        reaction.message.pin()

#If a user with the Max Host role removes a :pushpin: (📌) reaction from the message, the message will be unpinned
@client.event
async def on_reaction_remove(reaction, user):
    if  get(user.roles, name = "Max Host") and reaction.emoji == '📌':
        reaction.message.unpin()

#When bot is ready, open the commad channel
@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    commandChn = client.get_channel(COMMANDCHNNUM)

#runs the app
if __name__ == '__main__':
    client.run(os.environ.get('TOKEN'))

