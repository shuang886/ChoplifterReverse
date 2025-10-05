from PIL import Image
import sys, struct, re, math

# tracks addresses in the .s file (where the pointers can be found)
address = 0xa000
# tracks addresses in the asset blob (where the image assets can be found)
assetAddress = 0xa102

spriteTable = sys.stdout #open("sprites.s", "w")
spriteFile = open("CHOPGFX-generated", "wb")

# build a table of assets
def buildTable(name, comments, assets):
    global address, assetAddress
    for comment in comments:
        print(f"; {comment}", file=spriteTable)
    print(f"{name}:", file=spriteTable)
    for asset in assets:
        r = re.search(r"\w+ ([^\.]*)(\.w(\d+))?", asset)
        print(f"\t.word\t${assetAddress:04x}\t\t; ${address:04x}: {r.group(1)}", file=spriteTable)
        
        filename = "Resources/" + asset + ".png"
        image = Image.open(filename)
        
        # save starting position
        spriteFilePosition = spriteFile.tell()
        
        if r.group(3) is None:
            convertAsset(image)
        else:
            convertPreshiftedAsset(image, int(r.group(3)))
        
        address += 2
        image.close()
        assetAddress += spriteFile.tell() - spriteFilePosition
    print()

# convert a PNG to Choplifter's header-data format
def convertAsset(image):
    pixels = image.load()

    # write the width and height header
    spriteFile.write(struct.pack("=B", image.width))
    spriteFile.write(struct.pack("=B", image.height))
            
    # initialize with sentinel bit
    byte = 1
    # round up width to multiple of 8 px
    width = ((image.width + 7) // 8) * 8
    
    for h in range(0, image.height):
        for w in range(0, width):
            byte <<= 1
            
            # don't read past bounds
            if w < image.width:
                r, g, b = pixels[w, h]
                if r > 0 or g > 0 or b > 0:
                    byte |= 1
            
            # when sentinel bit hits 0x100, we've gotten 8 px from the image
            if byte & 0x100 > 0:
                spriteFile.write(struct.pack("=B", byte & 0xFF))
                byte = 1

# convert a PNG to Choplifter's header-data format
def convertPreshiftedAsset(image, realWidth):
    pixels = image.load()
    
    # write the width and height header
    spriteFile.write(struct.pack("=B", realWidth)) # 2 bpp
    spriteFile.write(struct.pack("=B", image.height))
            
    # initialize with sentinel bit
    byte = 0
    bit = 1
    width = math.ceil((realWidth + 7) / 7) * 7
    
    highBit = 0
    bits = [ -1, -1 ]
    for shift in range(0, 7):
        for h in range(0, image.height):
            byte = 0
            bit = 1 << shift
            bitsEmitted = 0
            for w in range(0, image.width):
                # don't read past bounds
                bits = [ -1, -1 ]
                if w < image.width:
                    r, g, b = pixels[w, h]
                    c = (r << 16) | (g << 8) | b
                    if c == 0x000000: # black0
                        highBit = 0
                        bits = [0, 0]
                    elif c == 0x75fb4c: # green
                        highBit = 0
                        bits = [0, 1]
                    elif c == 0xea33f7: # purple
                        highBit = 0
                        bits = [1, 0]
                    elif c == 0xd5d5d5: # white0
                        highBit = 0
                        bits = [1, 1]
                    elif c == 0x646464: # black1
                        highBit = 0x80
                        bits = [0, 0]
                    elif c == 0xec5e2a: # orange
                        highBit = 0x80
                        bits = [0, 1]
                    elif c == 0x4eacf8: # blue
                        highBit = 0x80
                        bits = [1, 0]
                    elif c == 0xffffff: # white1
                        highBit = 0x80
                        bits = [1, 1]
                    else:
                        print(f"unrecognized pixel color {c:06x} at {w}, {h}")
                
                # emit the first bit, if any
                if bits[0] >= 0:
                    if bits[0] > 0:
                        byte |= bit
                    bit <<= 1
                    if bit >= 0x80:
                        if bitsEmitted < width:
                            spriteFile.write(struct.pack("=B", highBit | (byte & 0x7F)))
                            bitsEmitted += 7
                        byte = 0
                        bit = 1
                
                # emit the second bit, if any
                if bits[1] >= 0:
                    if bits[1] > 0:
                        byte |= bit
                    bit <<= 1
                    if bit >= 0x80:
                        if bitsEmitted < width:
                            spriteFile.write(struct.pack("=B", highBit | (byte & 0x7F)))
                            bitsEmitted += 7
                        byte = 0
                        bit = 1
            # finishing up the row, emit any leftovers
            if bit > 1 and bitsEmitted < width:
                spriteFile.write(struct.pack("=B", highBit | (byte & 0x7F)))
                bitsEmitted += 7

# --- Main ---

print(f".org ${address:04x}\n", file=spriteTable)

#
# WARNING: The relative ordering of assets within each table is critical
#
buildTable("chopperSideSpriteTable",
    [
    "A list of the sprites needed for all sideways chopper angles.",
    "Same sprites are used for facing left and right, with renderer handling X-flip"
    ],
    [
    "Chopper -5 Full tilt forward, nose down",
    "Chopper -4 tilt forward",
    "Chopper -3 tilt forward",
    "Chopper -2 tilt forward",
    "Chopper -1 tilt forward",
    "Chopper No tilt",
    "Chopper +1 tilt backward",
    "Chopper +2 tilt backward",
    "Chopper +3 tilt backward",
    "Chopper +4 tilt backward",
    "Chopper +5 Full tilt backward, backward nose up",
    ])

buildTable("chopperHeadOnSpriteTable",
    [
    "A table of sprites to use when head-on or in rotation animation. Tilt is done with tilt-renderer"
    ],
    [
    "Chopper Normal head-on view, all tilt angles",
    "Chopper Partially rotated from head-on to sideways (frame 1)",
    "Chopper Partially rotated from head-on to sideways (frame 2)",
    "Chopper Partially rotated from head-on to sideways (frame 3)",
    "Chopper Partially rotated from head-on to sideways (frame 4)",
    ])

buildTable("chopperSquishingSpriteTable",
    [],
    [
    "Chopper Squished down a little sideways (mid-bounce)",
    "Chopper Squished down a little head-on (mid-bounce)",
    ])

buildTable("mainRotorAnimationTable",
    [],
    [
    "Chopper Main rotor (frame 1)",
    "Chopper Main rotor (frame 2)",
    "Chopper Main rotor (frame 3)",
    ])

buildTable("tailRotorAnimationTable",
    [],
    [
    "Chopper Tail rotor (frame 1)",
    "Chopper Tail rotor (frame 2)",
    "Chopper Tail rotor (frame 3)",
    "Chopper Tail rotor (frame 4)",
    ])

buildTable("jetMasterSpriteTable",
    [
    "All the sprite frames for rendering the enemy jets. Pointers into this come from jetSpriteTable"
    ],
    [
    "Jet Enemy jet, level flight",
    "Jet Enemy jet, turning (frame 1)",
    "Jet Enemy jet, turning (frame 2)",
    "Jet Enemy jet, turning (frame 3)",
    "Jet Enemy jet, turning (frame 4)",
    "Jet Enemy jet, turning (frame 5)",
    "Jet Enemy jet, turning (frame 6)",
    "Jet Enemy jet, turning (frame 7)",
    "Jet Enemy jet, turning (frame 8)",
    "Jet Enemy jet, turning (frame 9)",
    "Jet Enemy jet, turning (frame 10)",
    "Jet Enemy jet, turning (frame 11)",
    "Jet Enemy jet, turning (frame 12)",
    "Jet Enemy jet, turning (frame 13)",
    "Jet Enemy jet, turning (frame 14)",
    "Jet Enemy jet, turning (frame 15)",
    "Jet Enemy jet, turning (frame 16)",
    "Jet Enemy jet, turning (frame 17)",
    "Jet Enemy jet, turning (frame 18)",
    "Jet Enemy jet, turning (frame 19)",
    "Jet Enemy jet, turning (frame 20)",
    "Jet Enemy jet, turning (frame 21)",
    "Jet Enemy jet, turning (frame 22)",
    "Jet Enemy jet, turning (frame 23)",
    "Jet Enemy jet, turning (frame 24)",
    ])

buildTable("tankSpriteTable",
    [
    "All the sprite frames for rendering the enemy tanks"
    ],
    [
    "Tank Tank turret",
    "Tank Tank tread (frame 1)",
    "Tank Tank tread (frame 2)",
    ])

buildTable("tankCannonSpriteTable",
    [],
    [
    "Tank Tank cannon, facing full right",
    "Tank Tank cannon, facing up and right",
    "Tank Tank cannon, facing up",
    "Tank Tank cannon, facing up and left",
    "Tank Tank cannon, facing full left",
    ])

buildTable("bulletSpriteTable",
    [
    "All the sprites for the various bullets"
    ],
    [
    "Bullet Chopper bullet",
    "Bullet Tank shell",
    "Bullet Jet missile (The big ones fired in pairs at high altitude)",
    "Bullet Jet bomb (The little one that drops at an angle)",
    "Bullet Chopper muzzle flash",
    ])

buildTable("alienSpriteTable",
    [
    "All the sprites for the alien saucer"
    ],
    [
    "Alien Saucer body",
    "Alien Saucer mid section (frame 1)",
    "Alien Saucer mid section (frame 2)",
    "Alien Saucer mid section (frame 3)",
    ])

buildTable("explosionSpriteTable",
    [
    "All the sprite frames for rendering the explosions"
    ],
    [
    "Explosion Explosion (frame 1)",
    "Explosion Explosion (frame 2)",
    "Explosion Explosion (frame 3)",
    "Explosion Explosion (frame 4)",
    "Explosion Explosion (frame 5)",
    ])

buildTable("chopperRubbleSprite",
    [],
    [
    "Chopper Chopper rubble sprite",
    "Hostage Dying hostage",
    ])

buildTable("hostageRunningSpriteTable",
    [
    "All the sprite frames for rendering the hostages"
    ],
    [
    "Hostage Running man (frame 1)",
    "Hostage Running man (frame 2)",
    "Hostage Running man (frame 3)",
    "Hostage Running man (frame 4)",
    ])

buildTable("hostageWavingSpriteTable",
    [],
    [
    "Hostage Waving man (frame 1)",
    "Hostage Waving man (frame 2)",
    "Hostage Waving man (frame 3)",
    ])

buildTable("hostageLoadingSpriteTable",
    [],
    [
    "Hostage Man jumping into chopper (frame 1)",
    "Hostage Man jumping into chopper (frame 2)",
    ])

buildTable("mountainSpriteTable",
    [],
    [
    "Mountain Mountain 1.w48",
    "Mountain Mountain 2.w36",
    "Mountain Mountain 3.w54",
    "Mountain Mountain 4.w56",
    ])

buildTable("hudBorderSprite", [], [ "HUD Right border (green) of HUD" ])

buildTable("hudCornerSprite", [], [ "HUD Angled top corners of HUD" ])

buildTable("hudCornerSprite", [], [ "Base The orange main building of the base.w51" ])

buildTable("baseGrassCornerSprite", [], [ "Base The little corners of grass at the base" ])

buildTable("baseFlagpole", [], [ "Base The flag pole (without the flapping flag)" ])

buildTable("baseFlagSpriteTable",
    [],
    [
    "Base Flag animation (frame 1)",
    "Base Flag animation (frame 2)",
    ])

buildTable("baseLeftSidewalkSprite", [], [ "Base Little piece of sidewalk left of the base" ])

buildTable("baseRightSidewalkSprite", [], [ "Base Little piece of sidewalk right of the base" ])

buildTable("fenceTowerSprite4", [], [ "FenceTower Smallest (furthest) security fence tower" ])

buildTable("fenceTowerSprite3", [], [ "FenceTower 3" ])

buildTable("fenceTowerSprite2", [], [ "FenceTower 2" ])

buildTable("fenceTowerSprite1", [], [ "FenceTower 1" ])

buildTable("fenceTowerSprite0", [], [ "FenceTower Largest (closest) security fence tower" ])

buildTable("houseSpriteTable",
    [
    "All the sprites for the hostage houses"
    ],
    [
    "House Normal house.w27",
    "House House on fire.w27",
    ])

buildTable("houseSillSprite", [], [ "House The white strip along the bottom of the house" ])

buildTable("houseDebrisSprite", [], [ "House The debris in front of a burning house" ])

buildTable("houseFireSprites",
    [],
    [
    "House Fire animation (Frame 1)",
    "House Fire animation (Frame 2)",
    ])

buildTable("fontGraphicsTable",
    [
    "A list of pointers to all the font glyphs"
    ],
    [
    "FontGraphics 0",
    "FontGraphics 1",
    "FontGraphics 2",
    "FontGraphics 3",
    "FontGraphics 4",
    "FontGraphics 5",
    "FontGraphics 6",
    "FontGraphics 7",
    "FontGraphics 8",
    "FontGraphics 9",
    ])

buildTable("hudBubbleSprite", [], [ "HUD The little bubbles next to the HUD numbers" ])

buildTable("hudBackgroundBubbleSprite", [], [ "HUD The black background on the HUD numbers" ])

buildTable("titleGraphicsTable",
    [
    "A list of pointers to all the title graphic pieces"
    ],
    [
    "Title Your Mission- Rescue Hostages",
    "Title Choplifter logo",
    "Title Broderbund Presents",
    "Title Dan Gorlin logo",
    "Title The End",
    "Title Broderbund crown logo",
    ])

buildTable("sortieGraphicsTable",
    [
    "A list of pointers to all the font glyphs"
    ],
    [
    "Sortie First Sortie",
    "Sortie Second Sortie",
    "Sortie Third Sortie",
    ])

# the original file has an extraneous 0 byte in the end, matching it so binary diff can work
spriteFile.write(struct.pack("=B", 0))
