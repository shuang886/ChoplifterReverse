#
#  Makefile
#  Choplifter Reverse Engineer
#
#  Created by Quinn Dunki on May 5, 2024
#  https://blondihacks.com
#


CL65=cl65
CAD=./cadius
ADDR=800
LOADERADDR=300
VOLNAME=CHOPLIFTER
IMG=DiskImageParts
PGM=choplifter
EXECNAME=CHOP.SYSTEM\#FF2000
PYTHON=python

all: clean diskimage loader $(PGM) emulate

$(PGM): assets
	@PATH=$(PATH):/usr/local/bin; $(CL65) -C linkerConfig -t apple2 --start-addr $(ADDR) -l$(PGM).lst $(PGM).s
	$(CAD) ADDFILE $(VOLNAME).po /$(VOLNAME) CHOP0
	$(CAD) ADDFILE $(VOLNAME).po /$(VOLNAME) CHOP1
	$(CAD) ADDFILE $(VOLNAME).po /$(VOLNAME) CHOPGFX
	$(CAD) ADDFILE $(VOLNAME).po /$(VOLNAME) CHOPGFXHI
	rm -f $(PGM).o

diskimage:
	$(CAD) CREATEVOLUME $(VOLNAME).po $(VOLNAME) 143KB
	$(CAD) ADDFILE $(VOLNAME).po /$(VOLNAME) $(IMG)/PRODOS/PRODOS#FF0000
	
clean:
	rm -f $(PGM)
	rm -f $(PGM).o
	rm -f sprites.s chopgfx.bin chopgfx-lo.bin chopgfx-hi.bin

emulate:
		osascript V2Make.scpt $(PROJECT_DIR) $(VOLNAME)
	
assets:
	$(PYTHON) compile-assets.py
	split -b 7662 -d chopgfx.bin chopgfx-
	mv chopgfx-00 CHOPGFX
	mv chopgfx-01 CHOPGFXHI

loader:
	@PATH=$(PATH):/usr/local/bin; $(CL65) -C linkerConfigLoader -t apple2 --start-addr $(LOADERADDR) -lloader.lst loader.s -o $(EXECNAME)
	$(CAD) ADDFILE $(VOLNAME).po /$(VOLNAME) $(EXECNAME)
	rm -f $(LOADEREXEC)
	rm -f loader.o
