from PIL import Image
from collections import deque
import sys, struct, re, math, os.path

# tracks addresses in the .s file (where the pointers can be found)
address = 0xa000
# tracks addresses in the asset blob (where the image assets can be found)
# this *MUST* match the loader configuration
assetAddress = 0xa102

spriteTable = open("sprites.s", "w")
spriteFile = open("chopgfx.bin", "wb")

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
        
        # there are two kinds of image assets:
        # - normal sprite
        # - preshifted: 7 copies of the same thing, each shifted 1 bit to the right
        if r.group(3) is None:
            convertAsset(image)
        else:
            convertPreshiftedAsset(image)
        
        address += 2
        image.close()
        assetAddress += spriteFile.tell() - spriteFilePosition
    print(file=spriteTable)

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
def convertPreshiftedAsset(image):
    pixels = image.load()
    
    # image.width is actually doubled, because we had to account for a 2-bit pixel
    # split across two bytes that can have different high-bit settings.
    
    # write the width and height header
    spriteFile.write(struct.pack("=B", image.width))
    spriteFile.write(struct.pack("=B", image.height))
    
    expectedBytesPerRow = math.ceil((image.width + 7) / 7) # 7 padding, 7 bpp
    for shift in range(0, 7):
        lastHighBit = 0
        outputBits = deque()
        for h in range(0, image.height):
            # before starting each row, shift towards the right if needed
            outputMask = 1 << shift
            for _ in range(0, shift):
                outputBits.append(0)
            bytesEmittedForRow = 0
            readingBit0 = True
            for w in range(0, image.width):
                r, g, b = pixels[w, h]
                c = (r << 16) | (g << 8) | b
                if readingBit0:
                    if c == 0x000000 or c == 0x75fb4c: # black0, green (first bit 0)
                        outputBits.append(0)
                        lastHighBit = 0
                    elif c == 0xea33f7 or c == 0xd5d5d5: # purple, white0 (first bit 1)
                        outputBits.append(outputMask)
                        lastHighBit = 0
                    elif c == 0x646464 or c == 0xec5e2a: # black1, orange (first bit 0)
                        outputBits.append(0x80)
                        lastHighBit = 0x80
                    elif c == 0x4eacf8 or c == 0xffffff: # blue, white1 (first bit 1)
                        outputBits.append(0x80 | outputMask)
                        lastHighBit = 0x80
                    else:
                        print(f"⚠️ unrecognized pixel color {c:06x} at {w}, {h}")
                else:
                    if c == 0x000000 or c == 0xea33f7: # black0, purple (second bit 0)
                        outputBits.append(0)
                        lastHighBit = 0
                    elif c == 0x75fb4c or c == 0xd5d5d5: # green, white0 (second bit 1)
                        outputBits.append(outputMask)
                        lastHighBit = 0
                    elif c == 0x646464 or c == 0x4eacf8: # black1, blue (second bit 0)
                        outputBits.append(0x80)
                        lastHighBit = 0x80
                    elif c == 0xec5e2a or c == 0xffffff: # orange, white1 (second bit 1)
                        outputBits.append(0x80 | outputMask)
                        lastHighBit = 0x80
                    else:
                        print(f"⚠️ unrecognized pixel color {c:06x} at {w}, {h}")
                readingBit0 = not readingBit0
                outputMask <<= 1
                
                if outputMask >= 0x80:
                    byte = 0
                    for _ in range(0, 7):
                        byte |= outputBits.popleft()
                    spriteFile.write(struct.pack("=B", byte))
                    bytesEmittedForRow += 1
                    outputMask = 1
            
            # pad out the image with up to 7 more black bits
            for _ in range(0, 7 - shift):
                outputBits.append(lastHighBit)
            # output everything
            while len(outputBits) > 0:
                byte = 0
                for _ in range(0, 7):
                    if len(outputBits) > 0:
                        byte |= outputBits.popleft()
                spriteFile.write(struct.pack("=B", byte))
                bytesEmittedForRow += 1
            # sanity check
            if bytesEmittedForRow != expectedBytesPerRow:
                print(f"⚠️ {bytesEmittedForRow} bytes emitted for shift {shift} row {h}, expected {expectedBytesPerRow}")

# --- Main ---

print(f"; *** Automatically-generated by {os.path.basename(__file__)}, do not edit. ***\n", file=spriteTable)

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

buildTable("baseBuildingSprite", [], [ "Base The orange main building of the base.w51" ])

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

spriteFile.close()
spriteTable.close()
