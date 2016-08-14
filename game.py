import pygame #import all of pygame
from pygame.locals import *
import random #import rng for battle

import settings #load settings
import map #and map manager
import objects #and objects
import font #font manager
import player #class for player
import dialog #class for dialogs
import transition #import all the transitions
import menu #import menu manager
import battle
import data
import thread, traceback
try:
    import readline
except:
    pass
def evalinput(self) :
    while self.g.keeprunning :
        try :
            x = raw_input()
            print repr(eval(x))
        except : traceback.print_exc()


class Game:
    """
    Class for our game engine

    Attributes:
        g               Container object for global variables

        camera_follow   who the camera follows
        camera_pos      2-tuple representing default camera position
        curr_transition current transition object
        debug           whether we're in debug mode or not
        default_dialog
        dialog
        dialog_callback callback for dialog completion
        dialog_drawing  set when the dialog is showing text
        dialog_result   hold result of a dialog
        font
        map_image       the current map image
        menu            menu manager
        menu_showing    whether the menu is being shown
        obj2pos         dictionary of objects mapped to positions
        objects         dictionary of objects on the map
        player          Player object
        pos2obj         dictionary of positions mapped to objects
        stopped         set when things should stop moving
        surf            pygame.Surface to display on
        transition_cb   callback when transition completes
        warp_obj        warp object
        warps           dictionary of warps on the map
        wild_pokemon    array containing wild pokemon information
    """
    def __init__(self, g):
        self.g = g  # store global variables

        self.camera_follow = None
        self.camera_pos = [80, 128] #set default camera position
        self.curr_transition = None #current transition object
        self.debug = False #whether we're in debug mode or not
        self.default_dialog = dialog.Dialog(self.g, "standard")
        self.dialog = None
        self.dialog_callback = None #callback for dialog completion
        self.dialog_drawing = False #set when the dialog is showing text
        self.dialog_result = None #hold result of a dialog
        self.font = self.default_dialog.dlog_font
        self.map_image = None
        self.menu = menu.Menu(self) #initialize a menu manager
        self.menu_showing = False #whether the menu is being shown
        self.obj2pos = {} #dictionary of objects mapped to positions
        self.objects = {} #list of objects on the map
        self.player = None
        self.pos2obj = {} #dictionary of positions mapped to objects
        self.stopped = False #set when things should stop moving
        self.surf = pygame.Surface((settings.screen_x, settings.screen_y)) #create a new surface to display on
        self.surf.convert() #convert it to the display format for faster blitting
        self.transition_cb = None #callback when transition completes
        self.warp_obj = None #warp object
        self.warps = {} #list of warps on the map
        self.wild_pokemon = []

    def start(self):
        """
        Start the game
        """
        self.player = player.Player(self) #initialize a player object
        self.camera_follow = self.player #set who the camera follows
        self.load_map(self.g.save.get_game_prop("game", "curr_map", "maps/oasis_intro.xml")) #load map
        self.map_image = self.map.update() #update it once
        self.transition(transition.FadeIn(32)) #start fade in

    def load_map(self, map_file):
        """
        load a map from xml data and set it as this Game's map
        :param map_file: path to xml file containing map data
        """
        map_dom = data.load_xml(map_file).documentElement #load map xml data
        tile_file = map_dom.getAttribute("tiles") #get tile map file
        self.map = map.Map(self.g, tile_file)
        self.map_file = map_file
        self.wild_pokemon = {} #clear wild pokemon data too

        # loop that reads all the data from the xml file
        child = map_dom.firstChild
        while child is not None:
            if child.localName == "object":
                # parse object information and add it to the map
                obj_id = child.getAttribute("id")
                obj_type = child.getAttribute("type")
                obj = objects.obj_types[obj_type](self, child)
                self.objects[obj_id] = obj
                self.map.add_object(obj)
            elif child.localName == "wild":
                # parse wild pokemon information
                self.parse_wild(child)
            child = child.nextSibling

        self.objects["player"] = self.player
        self.map.add_object(self.player)
        if self.debug:
            print repr(self.objects)

    def parse_wild(self, wild):
        """
        parse wild pokemon data
        :param wild: an xml object containing information on wild pokemon
        """
        when = wild.getAttribute("for") #get when the data will be used
        data = []

        # loop through node data to get wild pokemon
        for node in wild.childNodes:
            if node.localName != "pokemon":
                continue
            name = node.getAttribute("type")
            levels = node.getAttribute("level").replace(" ", "")
            rarity = 1
            if node.getAttribute("rarity") != "":
                rarity = int(node.getAttribute("rarity"))

            # parse the level string
            # level strings are level ranges delimited by | characters
            # level ranges are of the form low-high, where low and high are integers
            # example: 6-8|12
            level_list = []
            for level in levels.split("|"):
                if "-" not in level:
                    level_list.append(int(level))
                else:
                    t = level.split("-") #get both parts of range
                    start, end = int(t[0]), int(t[1])+1 #parse it
                    level_list.extend(range(start, end)) #add range to levels

            t = [name, level_list] #generate data
            for x in xrange(rarity): #add it once for each rarity
                data.append(t)
        self.wild_pokemon[when] = data #add generated list to wild data
        if self.debug:
            print data

    def add_warp(self, pos, obj):
        """
        add a warp object to the warps dict
        :param pos: position of the warp
        :param obj: the warp object to store
        """
        self.warps[pos] = obj #store the warp

    def prepare_warp(self, pos):
        """
        prepare a warp after a transition.
        set the current warp object, and begin a fade out.
        after the fade out is done, a callback insues which loads
        the new map info and fades back in
        :param pos: the position of the warp object
        """
        self.warp_obj = self.warps[pos]
        self.transition(transition.FadeOut(32), callback=self.perform_warp)

    def clean_objects_to_defaults(self):
        """
        set various game variables to default values
        """
        self.camera_follow = self.player  # set who the camera follows
        self.objects = {}  # destroy map objects
        self.warps = {}
        self.map = None
        self.warp_obj = False
        self.obj2pos = {}
        self.pos2obj = {}
        self.dialog_drawing = False

    def perform_warp(self):
        """
        clean up information related to the current map, then warp
        to a new map specified by the current warp_obj.
        assumes that the screen has already performed a FadeOut, and will
        thus perform a FadeIn at the end.
        :return:
        """
        warp_obj = self.warp_obj
        #save object data before cleaning up
        for id in self.objects:
            self.objects[id].save()

        self.clean_objects_to_defaults()
        map_file = "maps/"+warp_obj["dest_map"] #get destination of warp
        self.load_map(map_file) #load the map
        new_warp = self.objects[warp_obj["dest_warp"]] #get the warp destination
        player = self.objects["player"] #get the player object
        new_pos = (new_warp.tile_x, new_warp.tile_y) #get warp destination
        player.tile_pos = new_pos[:] #set player position
        player.pos = [((player.tile_pos[0]-1)*16)+8, (player.tile_pos[1]-1)*16]
        player.rect = pygame.Rect(player.pos, player.size)
        self.map_image = self.map.update() #update map once
        self.transition(transition.FadeIn(32)) #start fade back in

    def get_tile_type(self, tile_x, tile_y, player_req=False):
        """
        get the type of tyle at the given position
        :param tile_x: x coordinate
        :param tile_y: y coordinate
        :param player_req: if its being requested by a player or not
        :return:
        """
        if tile_y < 0 or tile_x < 0: #if the tile is negative
            return -1 #it shouldn't exist
        try: #test if there's an object in the given position
            t = self.pos2obj[(tile_x, tile_y)] #get object
            if t != self.player or not player_req: #if it's not a player or not a player is requesting it
                if t.visible: #and it's visible
                    return -1 #say so
        except: #if there wasn't an object
            pass #don't do anything
        try: #try to get the tile
            return self.map.collision_map.tilemap[tile_y][tile_x]
        except: #if we can't
            return -1 #say so

    def collide(self, tile_pos):
        """
        test for collision type of a tile position
        :param tile_pos:
        :return:
        """
        type = self.get_tile_type(tile_pos[0], tile_pos[1]) #get tile type
        if type != settings.TILE_NORMAL: #if it's not a normal tile
            return True #this is a collison
        return False #otherwise, we're fine

    def set_obj_pos(self, obj, pos):
        """
        set an objects position
        :param obj: the object
        :param pos: the position as an array
        :return:
        """
        if pos is not None:
            pos = tuple(pos[:]) #convert position to tuple

        # clean out previous instances of the object
        if obj in self.obj2pos:
            del self.pos2obj[self.obj2pos[obj]]
            del self.obj2pos[obj]

        # if we supplied a position, put it there
        if pos is not None:
            self.obj2pos[obj] = pos
            self.pos2obj[pos] = obj

    def show_dlog(self, str, talker=None, dlog=self.default_dialog, callback=None):
        """
        draw a dialog
        :param str: the text to draw
        :param talker: the object that is talking
        :param dlog: a specific type of dialog
        :param callback: the callback to insue when the dialog is finished
        :return:
        """
        self.dialog_drawing = True
        self.dialog = dlog
        self.dialog.draw_text(str)
        self.dialog_talking = talker #store who's talking
        self.dialog_callback = callback #store callback
        self.dialog_result = None #clear result

    def interact(self, pos, direction):
        """
        interact with an object at a position, if it exists
        :param pos: the position to check
        :param direction: the direction from which we are trying to interact
        :return:
        """
        if pos in self.pos2obj: #if this position has an object
            self.pos2obj[pos].interact(direction) #tell the object to interact

    def transition(self, obj, callback=None):
        """
        register the objects related to a transition
        :param obj: the current translation object
        :param callback: the callback for when the transition is done
        :return:
        """
        self.curr_transition = obj
        self.transition_cb = callback

    def try_battle(self):
        """
        decide whether to run a battle or not
        :return: True if we should and we set up for a battle
                 None / void otherwise
        """
        t = random.randrange(1, 187/7) #decide whether a battle should happen
        if t == 1:
            if "grass" not in self.wild_pokemon:
                return #if there isn't proper wild data then return
            self.transition(transition.WavyScreen(), callback=self.setup_wild_battle) #start transition
            return True
        return

    def setup_wild_battle(self):
        """
        callback to setup and start a wild battle
        """
        # pick a random pokemon
        data = self.wild_pokemon["grass"]
        type = random.randrange(0, len(data))
        level = random.randrange(0, len(data[type][1]))

        # create the battle object and start the battle
        t = battle.Battle(self)
        t.start_wild(data[type][0], data[type][1][level])

    def update(self):
        """
        update the entire engine for this frame
        """
        if self.g.curr_keys[settings.key_debug]: #if the debug key is pressed
            self.debug = not self.debug #invert debug flag
            if self.debug :
                thread.start_new_thread(evalinput, (self,))
                self.g.keeprunning = True
            else :
                self.g.keeprunning = False
        if self.g.curr_keys[settings.key_menu]: #if the menu key is pressed
            #if no transition is happening and the menu isn't already being shown
            if self.curr_transition is None and self.menu_showing is False and self.dialog_drawing is False and self.stopped is False:
                self.menu.show() #show menu
                self.menu_showing = True #and mark it as being shown
        #center camera on player
        pos = self.camera_follow.pos #get position of what the camera is following
        self.camera_pos = (pos[0]-(settings.screen_x/2)+16, pos[1]-(settings.screen_y/2)+16)
        if self.curr_transition is None and self.menu_showing is False: #if there is no transition going on now
            self.map_image = self.map.update(pygame.Rect(self.camera_pos, \
            (settings.screen_x, settings.screen_y))) #update the map
            if self.debug: #if we're debugging
                if self.g.curr_keys[settings.key_dbg_save]: #if save key is pressed
                    self.save() #do a save
                elif self.g.curr_keys[settings.key_dbg_load]: #if load key is pressed
                    self.g.reset() #call game reset function
                    return self.surf #and return
        self.surf.fill((0, 0, 0)) #clear surface for black background
        if self.debug: #if we're in debug mode
            for pos in self.pos2obj: #draw object collision tiles
                self.map_image.fill((255, 0, 0), rect=pygame.Rect(((pos[0]*16, pos[1]*16), (16, 16))), special_flags=BLEND_RGB_MULT)
        #draw map
        self.surf.blit(self.map_image, (0, 0), pygame.Rect(self.camera_pos, \
            (settings.screen_x, settings.screen_y))) #blit it
        if self.menu_showing is True: #if the menu is being shown
            self.menu.update(self.surf) #update the menu
        if self.curr_transition is not None: #if there is a transition happening
            r = self.curr_transition.update(self.surf) #update it
            if r: #if it finished
                self.curr_transition = None #destroy transition object
                if self.transition_cb is not None: #if there is a callback
                    self.transition_cb() #call it            
                    self.transition_cb = None #destroy callback
        if self.dialog_drawing: #if we're drawing a dialog
            result = self.dialog.update(self.surf, (0, 1)) #draw it
            if result is not None: #if we're finished
                self.dialog_drawing = False #stop drawing
                self.dialog_result = result #store result
                if self.dialog_callback: #if there's a callback
                    self.dialog_callback(result) #call it with result
                self.dialog_callback = None #clear callback
            elif self.dialog_talking != None: #if somebody is talking
                #draw an arrow to them
                pos = self.dialog_talking.pos
                pos = (pos[0]-self.camera_pos[0]+2, pos[1]-self.camera_pos[1]+10)
                pygame.draw.polygon(self.surf, (161, 161, 161), [[63, 41], [pos[0]-1, pos[1]+1],[pos[0]+1, pos[1]+1],[81, 41]])
                self.dialog.update(self.surf, (0, 1))
                pygame.draw.polygon(self.surf, (255, 255, 255), [[64, 42], pos, [80, 42]])
        if self.debug: self.font.render(str(self.g.fps), self.surf, (0, 180)) #draw framerate
        return self.surf #return the rendered surface

    def save(self, fname=None):
        """
        save the game data
        :param fname: file name to save to, defaults to the name in the settings.py file
        :return:
        """
        for id in self.objects: #loop through all our objects
            self.objects[id].save() #tell them to save
        if fname is None: #if no save file was specified
            f = settings.save_name #use one in settings
        else: #otherwise
            f = fname #use passed one
        self.g.save.set_game_prop("game", "curr_map", self.map_file) #store map
        self.g.save.save(f) #write out save file
