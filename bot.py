#Chatty Bot
#Created for the r/PokemonMaxRaids discord server
#Authored by Ymir | Prince_of_Galar

#setup
import discord
import asyncio
from discord.utils import get

client = discord.Client() 

#If a user with the Max Host role adds a :pushpin: (📌) reaction to a message, the message will be pinned
@client.event
async def on_reaction_add(reaction, user):
    if get(user.roles, name = "Max Host") and reaction.emoji == '📌':
        await reaction.message.pin()

#If a user with the Max Host role removes a :pushpin: (📌) reaction from the message, the message will be unpinned
@client.event
async def on_reaction_remove(reaction, user):
    if  get(user.roles, name = "Max Host") and reaction.emoji == '📌':
            await reaction.message.unpin()

#runs the app
if __name__ == '__main__':
    client.run('Njc4MjYwNDEyNTQxODI5MTMw.XkgV2Q.KC7ciXL3ymkKfio-dF42dFSut3w') #Discord TOKEN string

#Last published February 15th, 2020
