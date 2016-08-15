import pygame #import everything pygame-related
from pygame.locals import *

import settings #load game settings
import game #and game engine
import savegame #load savegame manager
import titlescreen #load title screen
import error #load various errors

#import parts of game that need loading
import poke_types
import pokemon
import map

class Container: #blank class to store global variables
    pass
    
def wait_frame(g):
    """
    wait for the next frame, maintain fps limits
    :param g:
    :return:
    """
    g.next_frame += 1000.0/settings.framerate #calculate time of next frame
    now = pygame.time.get_ticks() #get current number of ticks
    g.next_fps += 1 #increment one frame
    if g.next_frame < now: #if we've already passed the next frame
        g.next_frame = now #try to go as fast as possible
    else: #if we haven't
        pygame.time.wait(int(g.next_frame)-now) #wait for next frame
    if now / 1000 != g.prev_secs: #if one frame has passed
        g.fps = g.next_fps #set framerate
        g.next_fps = 0 #clear next framerate
        g.prev_secs = now/1000 #store the second this number was calculated

def reset(g):
    """
    reset the game
    :param g: Container for global variables
    :return:
    """
    g.game = None #destroy current game
    g.save.new() #create a new save file
    g.title_screen = titlescreen.TitleScreen(g) #initialize title screen
    g.update_func = g.title_screen.update #set update function

def mainloop(g):
    """
    main loop of the game
    :param g: Container for global variables
    """
    running = True
    while running:
        # handle pygame events
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
                break
            elif event.type == KEYDOWN:
                if event.key in settings.keys:
                    index = settings.keys.index(event.key)
                    g.keys[index] = True
            elif event.type == KEYUP:
                if event.key in settings.keys:
                    index = settings.keys.index(event.key)
                    g.keys[index] = False

        # check quitting conditions
        if g.keys[settings.key_escape] == True:
            break
        if running == False:
            break

        #update key variables
        for x in xrange(len(settings.keys)):
            # update key states if they have changed
            t = g.keys[x] ^ g.old_keys[x]
            t = t & g.keys[x]
            g.curr_keys[x] = t
            g.old_keys[x] = g.keys[x]

        # update graphics
        surface = g.update_func()
        pygame.transform.scale(surface, (settings.screen_x*settings.screen_scale, \
            settings.screen_y*settings.screen_scale), g.screen)
        pygame.display.flip()

        # wait for the next frame
        wait_frame(g)

if __name__=="__main__":
    g = Container() #get the global variable container

    g.keys = [False]*len(settings.keys) #variable to hold states of keys
    g.old_keys = [False]*len(settings.keys) #and previous keys
    g.curr_keys = [False]*len(settings.keys) #only true when key has been pressed this frame

    screen = pygame.display.set_mode((settings.screen_x*settings.screen_scale, \
        settings.screen_y*settings.screen_scale)) #create a window to draw on
    g.screen = screen #store it in the globals
    pygame.display.set_caption("Pokeclone") #set screen title

    g.next_frame = 0 #tick number of the next frame
    g.fps = 0 #current FPS
    g.next_fps = 0 #next FPS
    g.prev_secs = 0 #previous number of seconds

    g.reset = lambda: reset(g) #store reset handler

    #start the game running
    try:
        poke_types.load_data() #load pokemon type data
        pokemon.load_data()
        map.load_data()
        g.save = savegame.SaveGame(g) #initialize a new savegame manager
        reset(g) #reset the game
        mainloop(g) #start the main loop
    except error.QuitException: #if it was just a forced quit
        pass #don't do anything
    except Exception as e: #if it's any other exception
        error.exception_handler(g, e) #pass it to exception handler
    g.keeprunning = False
