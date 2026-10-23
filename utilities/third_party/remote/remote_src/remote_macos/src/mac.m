// Portions Copyright (c) 2026 Microsoft Corporation

/*
 *  OSXvnc Copyright (C) 2001 Dan McGuirk <mcguirk@incompleteness.net>.
 *  Original Xvnc code Copyright (C) 1999 AT&T Laboratories Cambridge.  
 *  All Rights Reserved.
 * 
 * Cut in two parts by Johannes Schindelin (2001): libvncserver and OSXvnc.
 * 
 * Completely revamped and adapted to work with contemporary APIs by Christian Beier (2020).
 * 
 * This file implements every system specific function for Mac OS X.
 * 
 *  It includes the keyboard function:
 * 
     void KbdAddEvent(down, keySym, cl)
        rfbBool down;
        rfbKeySym keySym;
        rfbClientPtr cl;
 * 
 *  the mouse function:
 * 
     void PtrAddEvent(buttonMask, x, y, cl)
        int buttonMask;
        int x;
        int y;
        rfbClientPtr cl;
 * 
 */

#include <AppKit/AppKit.h>
#include <Carbon/Carbon.h>
#include <CoreMedia/CoreMedia.h>
#include <ScreenCaptureKit/ScreenCaptureKit.h>
#include <rfb/rfb.h>
#include <rfb/keysym.h>
#include <IOKit/pwr_mgt/IOPMLib.h>
#include <IOKit/pwr_mgt/IOPM.h>
#include <stdio.h>
#include <pthread.h>
#include <stdlib.h>

#import "ScreenCapturer.h"

#define MAX_WAIT_TIME_SEC 120

/* The main LibVNCServer screen object */
rfbScreenInfoPtr rfbScreen;

/* Two framebuffers. */
void *frameBufferOne;
void *frameBufferTwo;

/* Pointer to the current backbuffer. */
void *backBuffer;

/* The multi-sceen display number chosen by the user */
int displayNumber = -1;
/* The corresponding multi-sceen display ID */
CGDirectDisplayID displayID;

/* The server's private event source */
CGEventSourceRef eventSource;

/* a dictionary mapping characters to keycodes */
CFMutableDictionaryRef charKeyMap;

/* a dictionary mapping characters obtained by Shift to keycodes */
CFMutableDictionaryRef charShiftKeyMap;

/* a dictionary mapping characters obtained by Alt-Gr to keycodes */
CFMutableDictionaryRef charAltGrKeyMap;

/* a dictionary mapping characters obtained by Shift+Alt-Gr to keycodes */
CFMutableDictionaryRef charShiftAltGrKeyMap;

/* a table mapping special keys to keycodes. static as these are layout-independent */
static int specialKeyMap[] = {
    /* "Special" keys */
    XK_space,             49,      /* Space */
    XK_Return,            36,      /* Return */
    XK_Delete,           117,      /* Delete */
    XK_Tab,               48,      /* Tab */
    XK_Escape,            53,      /* Esc */
    XK_Caps_Lock,         57,      /* Caps Lock */
    XK_Num_Lock,          71,      /* Num Lock */
    XK_Scroll_Lock,      107,      /* Scroll Lock */
    XK_Pause,            113,      /* Pause */
    XK_BackSpace,         51,      /* Backspace */
    XK_Insert,           114,      /* Insert */

    /* Cursor movement */
    XK_Up,               126,      /* Cursor Up */
    XK_Down,             125,      /* Cursor Down */
    XK_Left,             123,      /* Cursor Left */
    XK_Right,            124,      /* Cursor Right */
    XK_Page_Up,          116,      /* Page Up */
    XK_Page_Down,        121,      /* Page Down */
    XK_Home,             115,      /* Home */
    XK_End,              119,      /* End */

    /* Numeric keypad */
    XK_KP_0,              82,      /* KP 0 */
    XK_KP_1,              83,      /* KP 1 */
    XK_KP_2,              84,      /* KP 2 */
    XK_KP_3,              85,      /* KP 3 */
    XK_KP_4,              86,      /* KP 4 */
    XK_KP_5,              87,      /* KP 5 */
    XK_KP_6,              88,      /* KP 6 */
    XK_KP_7,              89,      /* KP 7 */
    XK_KP_8,              91,      /* KP 8 */
    XK_KP_9,              92,      /* KP 9 */
    XK_KP_Enter,          76,      /* KP Enter */
    XK_KP_Decimal,        65,      /* KP . */
    XK_KP_Add,            69,      /* KP + */
    XK_KP_Subtract,       78,      /* KP - */
    XK_KP_Multiply,       67,      /* KP * */
    XK_KP_Divide,         75,      /* KP / */

    /* Function keys */
    XK_F1,               122,      /* F1 */
    XK_F2,               120,      /* F2 */
    XK_F3,                99,      /* F3 */
    XK_F4,               118,      /* F4 */
    XK_F5,                96,      /* F5 */
    XK_F6,                97,      /* F6 */
    XK_F7,                98,      /* F7 */
    XK_F8,               100,      /* F8 */
    XK_F9,               101,      /* F9 */
    XK_F10,              109,      /* F10 */
    XK_F11,              103,      /* F11 */
    XK_F12,              111,      /* F12 */

    /* Modifier keys */
    XK_Shift_L,           56,      /* Shift Left */
    XK_Shift_R,           56,      /* Shift Right */
    XK_Control_L,         59,      /* Ctrl Left */
    XK_Control_R,         59,      /* Ctrl Right */
    XK_Meta_L,            58,      /* Logo Left (-> Option) */
    XK_Meta_R,            58,      /* Logo Right (-> Option) */
    XK_Alt_L,             55,      /* Alt Left (-> Command) */
    XK_Alt_R,             55,      /* Alt Right (-> Command) */
    XK_ISO_Level3_Shift,  61,      /* Alt-Gr (-> Option Right) */
    // 0x1008FF2B,           63,      /* Fn */

    /* Weirdness I can't figure out */
#if 0
    XK_3270_PrintScreen,     105,     /* PrintScrn */
    ???  94,          50,      /* International */
    XK_Menu,              50,      /* Menu (-> International) */
#endif
};

/* Global shifting modifier states */
rfbBool isShiftDown;
rfbBool isAltGrDown;

rfbBool clientConnected;

volatile BOOL ignoreClipboardUpdate = FALSE;

/*
  Synthesize a keyboard event. This is not called on the main thread due to rfbRunEventLoop(..,..,TRUE), but it works.
  We first look up the incoming keysym in the keymap for special keys (and save state of the shifting modifiers).
  If the incoming keysym does not map to a special key, the char keymaps pertaining to the respective shifting modifier are used
  in order to allow for keyboard combos with other modifiers.
  As a last resort, the incoming keysym is simply used as a Unicode value. This way MacOS does not support any modifiers though.
*/
void
KbdAddEvent(rfbBool down, rfbKeySym keySym, struct _rfbClientRec* cl)
{
    int i;
    CGKeyCode keyCode = -1;
    CGEventRef keyboardEvent;
    int specialKeyFound = 0;

    /* look for special key */
    for (i = 0; i < (sizeof(specialKeyMap) / sizeof(int)); i += 2) {
        if (specialKeyMap[i] == keySym) {
            keyCode = specialKeyMap[i+1];
            specialKeyFound = 1;
            break;
        }
    }

    if(specialKeyFound) {
	/* keycode for special key found */
	keyboardEvent = CGEventCreateKeyboardEvent(eventSource, keyCode, down);
	/* save state of shifting modifiers */
	if(keySym == XK_ISO_Level3_Shift)
	    isAltGrDown = down;
	if(keySym == XK_Shift_L || keySym == XK_Shift_R)
	    isShiftDown = down;

    } else {
	/* look for char key */
	size_t keyCodeFromDict;
	CFStringRef charStr = CFStringCreateWithCharacters(kCFAllocatorDefault, (UniChar*)&keySym, 1);
	CFMutableDictionaryRef keyMap = charKeyMap;
	if(isShiftDown && !isAltGrDown)
	    keyMap = charShiftKeyMap;
	if(!isShiftDown && isAltGrDown)
	    keyMap = charAltGrKeyMap;
	if(isShiftDown && isAltGrDown)
	    keyMap = charShiftAltGrKeyMap;

	if (CFDictionaryGetValueIfPresent(keyMap, charStr, (const void **)&keyCodeFromDict)) {
	    /* keycode for ASCII key found */
	    keyboardEvent = CGEventCreateKeyboardEvent(eventSource, keyCodeFromDict, down);
	} else {
	    /* last resort: use the symbol's utf-16 value, does not support modifiers though */
	    keyboardEvent = CGEventCreateKeyboardEvent(eventSource, 0, down);
	    CGEventKeyboardSetUnicodeString(keyboardEvent, 1, (UniChar*)&keySym);
        }

	CFRelease(charStr);
    }

    CGEventFlags flags = CGEventGetFlags(keyboardEvent);

    if (isShiftDown) {
        flags |= kCGEventFlagMaskShift;
    } else {
        flags &= ~kCGEventFlagMaskShift;
    }

    // Unset fn flag as it is being set on arrow keys for unknown reasons
    flags &= ~kCGEventFlagMaskSecondaryFn;

    CGEventSetFlags(keyboardEvent, flags);

    CGEventPost(kCGSessionEventTap, keyboardEvent);
    CFRelease(keyboardEvent);
}

/* Synthesize a mouse event. This is not called on the main thread due to rfbRunEventLoop(..,..,TRUE), but it works. */
void
PtrAddEvent(int buttonMask, int x, int y, rfbClientPtr cl)
{
    CGPoint position;
    CGRect displayBounds = CGDisplayBounds(displayID);
    CGEventRef mouseEvent = NULL;

    position.x = x + displayBounds.origin.x;
    position.y = y + displayBounds.origin.y;

    /* map buttons 4 5 6 7 to scroll events as per https://github.com/rfbproto/rfbproto/blob/master/rfbproto.rst#745pointerevent */
    if(buttonMask & (1 << 3))
	mouseEvent = CGEventCreateScrollWheelEvent(eventSource, kCGScrollEventUnitLine, 2, 1, 0);
    if(buttonMask & (1 << 4))
	mouseEvent = CGEventCreateScrollWheelEvent(eventSource, kCGScrollEventUnitLine, 2, -1, 0);
    if(buttonMask & (1 << 5))
	mouseEvent = CGEventCreateScrollWheelEvent(eventSource, kCGScrollEventUnitLine, 2, 0, 1);
    if(buttonMask & (1 << 6))
	mouseEvent = CGEventCreateScrollWheelEvent(eventSource, kCGScrollEventUnitLine, 2, 0, -1);

    if (mouseEvent) {
	CGEventPost(kCGSessionEventTap, mouseEvent);
	CFRelease(mouseEvent);
    }
    else {
	/*
	  Use the deprecated CGPostMouseEvent API here as we get a buttonmask plus position which is pretty low-level
	  whereas CGEventCreateMouseEvent is expecting higher-level events. This allows for direct injection of
	  double clicks and drags whereas we would need to synthesize these events for the high-level API.
	 */
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
	CGPostMouseEvent(position, TRUE, 3,
			 (buttonMask & (1 << 0)) ? TRUE : FALSE,
			 (buttonMask & (1 << 2)) ? TRUE : FALSE,
			 (buttonMask & (1 << 1)) ? TRUE : FALSE);
#pragma clang diagnostic pop
    }
}


/*
  Initialises keyboard handling:
  This creates four keymaps mapping UniChars to keycodes for the current keyboard layout with no shifting modifiers, Shift, Alt-Gr and Shift+Alt-Gr applied, respectively.
 */
rfbBool keyboardInit()
{
    size_t i, keyCodeCount=128;
    TISInputSourceRef currentKeyboard = TISCopyCurrentKeyboardInputSource();
    const UCKeyboardLayout *keyboardLayout;

    if(!currentKeyboard) {
	rfbErr("Could not get current keyboard info\n");
	return FALSE;
    }

    keyboardLayout = (const UCKeyboardLayout *)CFDataGetBytePtr(TISGetInputSourceProperty(currentKeyboard, kTISPropertyUnicodeKeyLayoutData));

    rfbLog("Found keyboard layout '%s'\n", CFStringGetCStringPtr(TISGetInputSourceProperty(currentKeyboard, kTISPropertyInputSourceID), kCFStringEncodingUTF8));

    charKeyMap = CFDictionaryCreateMutable(kCFAllocatorDefault, keyCodeCount, &kCFCopyStringDictionaryKeyCallBacks, NULL);
    charShiftKeyMap = CFDictionaryCreateMutable(kCFAllocatorDefault, keyCodeCount, &kCFCopyStringDictionaryKeyCallBacks, NULL);
    charAltGrKeyMap = CFDictionaryCreateMutable(kCFAllocatorDefault, keyCodeCount, &kCFCopyStringDictionaryKeyCallBacks, NULL);
    charShiftAltGrKeyMap = CFDictionaryCreateMutable(kCFAllocatorDefault, keyCodeCount, &kCFCopyStringDictionaryKeyCallBacks, NULL);

    if(!charKeyMap || !charShiftKeyMap || !charAltGrKeyMap || !charShiftAltGrKeyMap) {
	rfbErr("Could not create keymaps\n");
	return FALSE;
    }

    /* Loop through every keycode to find the character it is mapping to. */
    for (i = 0; i < keyCodeCount; ++i) {
	UInt32 deadKeyState = 0;
	UniChar chars[4];
	UniCharCount realLength;
	UInt32 m, modifiers[] = {0, kCGEventFlagMaskShift, kCGEventFlagMaskAlternate, kCGEventFlagMaskShift|kCGEventFlagMaskAlternate};

	/* do this for no modifier, shift and alt-gr applied */
	for(m = 0; m < sizeof(modifiers) / sizeof(modifiers[0]); ++m) {
	    UCKeyTranslate(keyboardLayout,
			   i,
			   kUCKeyActionDisplay,
			   (modifiers[m] >> 16) & 0xff,
			   LMGetKbdType(),
			   kUCKeyTranslateNoDeadKeysBit,
			   &deadKeyState,
			   sizeof(chars) / sizeof(chars[0]),
			   &realLength,
			   chars);

	    CFStringRef string = CFStringCreateWithCharacters(kCFAllocatorDefault, chars, 1);
	    if(string) {
		switch(modifiers[m]) {
		case 0:
		    CFDictionaryAddValue(charKeyMap, string, (const void *)i);
		    break;
		case kCGEventFlagMaskShift:
		    CFDictionaryAddValue(charShiftKeyMap, string, (const void *)i);
		    break;
		case kCGEventFlagMaskAlternate:
		    CFDictionaryAddValue(charAltGrKeyMap, string, (const void *)i);
		    break;
		case kCGEventFlagMaskShift|kCGEventFlagMaskAlternate:
		    CFDictionaryAddValue(charShiftAltGrKeyMap, string, (const void *)i);
		    break;
		}

		CFRelease(string);
	    }
	}
    }

    CFRelease(currentKeyboard);

    return TRUE;
}


void clientGone(rfbClientPtr cl)
{
    rfbShutdownServer(cl->screen, TRUE);
}


enum rfbNewClientAction newClient(rfbClientPtr cl)
{
  if(clientConnected)
    return (RFB_CLIENT_REFUSE);

  clientConnected = TRUE;

  cl->clientGoneHook = clientGone;
  return(RFB_CLIENT_ACCEPT);
}


static void handleClientXCutText(char* text, int len, rfbClientPtr cl)
{
    if (len < 0 || (len > 0 && text == NULL))
        return;

    if (len > 0 && text[len - 1] == '\0')
        len--;

    @autoreleasepool {
        NSString* value;

        if (len == 0) {
            value = @"";
        } else {
            value = [[NSString alloc] initWithBytes:text
                                      length:(NSUInteger)len
                                      encoding:NSUTF8StringEncoding];
        }

        if (value == nil)
            return;

        NSPasteboard* pasteboard = [NSPasteboard generalPasteboard];

        ignoreClipboardUpdate = TRUE;

        [pasteboard clearContents];

        BOOL success = [pasteboard setString:value
                                   forType:NSPasteboardTypeString];

        if (!success) {
            ignoreClipboardUpdate = FALSE;
        }
    }
}


static void* clipboardLocalHandler(void* param)
{
    @autoreleasepool {
        NSPasteboard* pasteboard  = [NSPasteboard generalPasteboard];
        NSInteger lastChangeCount = pasteboard.changeCount;

        while (TRUE) {
            @autoreleasepool {
                NSInteger currentChangeCount = pasteboard.changeCount;

                if (currentChangeCount != lastChangeCount) {
                    lastChangeCount = currentChangeCount;

                    if (ignoreClipboardUpdate) {
                        ignoreClipboardUpdate = FALSE;
                    } else {
                        NSString* text = [pasteboard stringForType:NSPasteboardTypeString];

                        if (text != nil) {
                            NSData* data = [text dataUsingEncoding:NSUTF8StringEncoding];

                            if (data != nil && data.length <= INT_MAX) {
                                rfbSendServerCutTextUTF8(rfbScreen, (char*)data.bytes, (int)data.length, NULL, 0);
                            }
                        } else {
                            rfbSendServerCutTextUTF8(rfbScreen, "", 0, NULL, 0);
                        }
                    }
                }
            }

            // Poll every 200ms
            struct timespec delay = {
                .tv_sec = 0,
                .tv_nsec = 200 * 1000 * 1000
            };
            nanosleep(&delay, NULL);
        }
    }

    return NULL;
}


rfbBool
ScreenInit(int argc, char**argv)
{
  int bitsPerSample = 8;
  CGDisplayCount displayCount;
  CGDirectDisplayID displays[32];

  /* grab the active displays */
  CGGetActiveDisplayList(32, displays, &displayCount);
  for (int i=0; i<displayCount; i++) {
      CGRect bounds = CGDisplayBounds(displays[i]);
      rfbLog("Found %s display %d at (%d,%d) and a resolution of %dx%d\n", (CGDisplayIsMain(displays[i]) ? "primary" : "secondary"), i, (int)bounds.origin.x, (int)bounds.origin.y, (int)bounds.size.width, (int)bounds.size.height);
  }
  if(displayNumber < 0) {
      rfbLog("Using primary display as a default\n");
      displayID = CGMainDisplayID();
  } else if (displayNumber < displayCount) {
      rfbLog("Using specified display %d\n", displayNumber);
      displayID = displays[displayNumber];
  } else {
      rfbErr("Specified display %d does not exist\n", displayNumber);
      return FALSE;
  }


  rfbScreen = rfbGetScreen(&argc,argv,
			   CGDisplayPixelsWide(displayID),
			   CGDisplayPixelsHigh(displayID),
			   bitsPerSample,
			   3,
			   4);

  rfbLog("Remote start\n");

  if(!rfbScreen) {
      rfbErr("Could not init rfbScreen.\n");
      return FALSE;
  }

  rfbScreen->port = 5901;

  rfbScreen->newClientHook = newClient;

  rfbScreen->desktopName    = "Remote";
  rfbScreen->neverShared    = TRUE;
  rfbScreen->dontDisconnect = TRUE;

  rfbScreen->deferUpdateTime   = 0;
  rfbScreen->maxRectsPerUpdate = 500; 

  rfbScreen->setXCutTextUTF8 = handleClientXCutText;

  rfbScreen->serverFormat.redShift = bitsPerSample*2;
  rfbScreen->serverFormat.greenShift = bitsPerSample*1;
  rfbScreen->serverFormat.blueShift = 0;

  gethostname(rfbScreen->thisHost, 255);

  frameBufferOne = malloc(CGDisplayPixelsWide(displayID) * CGDisplayPixelsHigh(displayID) * 4);
  frameBufferTwo = malloc(CGDisplayPixelsWide(displayID) * CGDisplayPixelsHigh(displayID) * 4);

  /* back buffer */
  backBuffer = frameBufferOne;
  /* front buffer */
  rfbScreen->frameBuffer = frameBufferTwo;

  /* we already capture the cursor in the framebuffer */
  rfbScreen->cursor = NULL;

  rfbScreen->ptrAddEvent = PtrAddEvent;
  rfbScreen->kbdAddEvent = KbdAddEvent;

  ScreenCapturer *capturer = [[ScreenCapturer alloc] initWithDisplay: displayID
                                                               width: CGDisplayPixelsWide(displayID)
                                                              height: CGDisplayPixelsHigh(displayID)
                                                        frameHandler:^(CMSampleBufferRef sampleBuffer) {
          rfbClientIteratorPtr iterator;
          rfbClientPtr cl;

          CGRect dirtyRects[64];
          int dirtyRectCount = 0;
          static unsigned long frameCount = 0;
          rfbBool fullUpdate = (frameCount % 300) == 0; /* full update every 300 frames as a safety net */
          frameCount++;

           /*
             Copy new frame to back buffer.
           */
          CVPixelBufferRef pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer);
          if(!pixelBuffer)
              return;

          CVPixelBufferLockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);

          if(CVPixelBufferGetWidth(pixelBuffer) != CGDisplayPixelsWide(displayID)
             || CVPixelBufferGetHeight(pixelBuffer) != CGDisplayPixelsHigh(displayID)) {
              static rfbBool sizeMismatchLogged = FALSE;
              if(!sizeMismatchLogged) {
                  rfbErr("Captured frame is %ldx%ld, but framebuffer is %zux%zu - skipping frame\n",
                          (long)CVPixelBufferGetWidth(pixelBuffer), (long)CVPixelBufferGetHeight(pixelBuffer),
                          CGDisplayPixelsWide(displayID), CGDisplayPixelsHigh(displayID));
                  sizeMismatchLogged = TRUE;
              }
              CVPixelBufferUnlockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);
              return;
          }

          /*
            Copy row by row: the pixel buffer's bytesPerRow can include padding,
            so a single flat memcpy of the whole buffer would shear the image.
          */
          {
              const uint8_t *srcBase = CVPixelBufferGetBaseAddress(pixelBuffer);
              size_t srcBytesPerRow = CVPixelBufferGetBytesPerRow(pixelBuffer);
              uint8_t *dstBase = backBuffer;
              size_t dstBytesPerRow = CGDisplayPixelsWide(displayID) * 4;
              size_t bytesPerRowToCopy = srcBytesPerRow < dstBytesPerRow ? srcBytesPerRow : dstBytesPerRow;

              for(size_t y = 0; y < CGDisplayPixelsHigh(displayID); ++y)
                  memcpy(dstBase + y * dstBytesPerRow,
                         srcBase + y * srcBytesPerRow,
                         bytesPerRowToCopy);
          }

          CVPixelBufferUnlockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);

          /*
            ScreenCaptureKit tags every frame with the rects that actually changed
            since the previous one (macOS 14+). Using them instead of marking the
            whole framebuffer drastically reduces the amount of data sent to
            clients. The key is spelled as a literal string so the binary still
            loads on older macOS, where we fall back to marking everything.
          */
          if(!fullUpdate) {
              CFArrayRef dirtyRectArray = NULL;
              if(@available(macOS 14.0, *))
                  dirtyRectArray = (CFArrayRef)CMGetAttachment(sampleBuffer, (__bridge CFStringRef)@"SCStreamFrameInfoDirtyRects", NULL);
              if(dirtyRectArray) {
                  CGRect bounds = CGRectMake(0, 0, CGDisplayPixelsWide(displayID), CGDisplayPixelsHigh(displayID));
                  CFIndex i, count = CFArrayGetCount(dirtyRectArray);
                  for(i = 0; i < count && dirtyRectCount < 64; ++i) {
                      CGRect rect;
                      if(CGRectMakeWithDictionaryRepresentation((CFDictionaryRef)CFArrayGetValueAtIndex(dirtyRectArray, i), &rect)) {
                          rect = CGRectIntersection(rect, bounds);
                          if(!CGRectIsEmpty(rect))
                              dirtyRects[dirtyRectCount++] = rect;
                      }
                  }
              }
          }

          /* Lock out client reads. */
          iterator=rfbGetClientIterator(rfbScreen);
          while((cl=rfbClientIteratorNext(iterator))) {
              LOCK(cl->sendMutex);
          }
          rfbReleaseClientIterator(iterator);

          /* Swap framebuffers. */
          if (backBuffer == frameBufferOne) {
              backBuffer = frameBufferTwo;
              rfbScreen->frameBuffer = frameBufferOne;
          } else {
              backBuffer = frameBufferOne;
              rfbScreen->frameBuffer = frameBufferTwo;
          }

          /*
            Mark the changed regions in the new framebuffer. Rects are in the
            stream's coordinate space, which matches the framebuffer 1:1.
          */
          if(dirtyRectCount == 0) {
              rfbMarkRectAsModified(rfbScreen, 0, 0, CGDisplayPixelsWide(displayID), CGDisplayPixelsHigh(displayID));
          } else {
              int i;
              for(i = 0; i < dirtyRectCount; ++i) {
                  CGRect rect = dirtyRects[i];
                  rfbMarkRectAsModified(rfbScreen,
                                        (int)rect.origin.x,
                                        (int)rect.origin.y,
                                        (int)ceil(rect.origin.x + rect.size.width),
                                        (int)ceil(rect.origin.y + rect.size.height));
              }
          }

          /* Swapping framebuffers finished, reenable client reads. */
          iterator=rfbGetClientIterator(rfbScreen);
          while((cl=rfbClientIteratorNext(iterator))) {
              UNLOCK(cl->sendMutex);
          }
          rfbReleaseClientIterator(iterator);

      } errorHandler:^(NSError *error) {
          rfbErr("Error: %s\n", [error.description UTF8String]);
          if(error.code == SCStreamErrorUserDeclined) {
              rfbErr("Could not get screen contents. Check if the program has been given screen recording permissions in 'System Preferences'->'Security & Privacy'->'Privacy'->'Screen Recording'.\n");
          }
          rfbShutdownServer(rfbScreen, TRUE);
      }];
  [capturer startCapture];

  rfbInitServer(rfbScreen);

  return TRUE;
}

static void* timeoutHandler(void* param)
{
    sleep(MAX_WAIT_TIME_SEC);

    if (!clientConnected)
    {
        rfbLog("Timeout reached, no client connected\n");
        rfbShutdownServer(rfbScreen, TRUE);
    }

    return NULL;
}

static void signalHandler(int sig)
{
    rfbShutdownServer(rfbScreen, TRUE);
}

int main(int argc,char *argv[])
{
  int i;

  for(i=argc-1;i>0;i--)
    if(strcmp(argv[i],"-logEnable")==0) {
      rfbLogEnable(TRUE);
    } else if(strcmp(argv[i],"-display")==0) {
	displayNumber = atoi(argv[i+1]);
    } else if(strcmp(argv[i],"-h") == 0 || strcmp(argv[i],"--help") == 0)  {
        fprintf(stderr, "-display <index>       Only export specified display\n");
        rfbUsage();
        exit(EXIT_SUCCESS);
    }

  if(!AXIsProcessTrusted()) {
      fprintf(stderr, "The application does not have the necessary system permission. Please check if the program has been given permission to control your computer in 'System Preferences'->'Security & Privacy'->'Privacy'->'Accessibility'.\n");
      exit(1);
  }

  /* Create a private event source for the server. This helps a lot with modifier keys getting stuck on the OS side
     (but does not completely mitigate the issue: For this, we keep track of modifier key state and set it specifically
     for the generated keyboard event in the keyboard event handler). */
  eventSource = CGEventSourceCreate(kCGEventSourceStatePrivate);

  if(!keyboardInit())
      exit(1);

  if(!ScreenInit(argc,argv))
      exit(1);

  pthread_t timeoutThread;
  pthread_create(&timeoutThread, NULL, timeoutHandler, NULL);
  pthread_detach(timeoutThread);

  pthread_t clipboardThread;
  pthread_create(&clipboardThread, NULL, clipboardLocalHandler, NULL);
  pthread_detach(clipboardThread);

  struct sigaction sa = {};
  sa.sa_handler = signalHandler;
  sigemptyset(&sa.sa_mask);

  sigaction(SIGINT,  &sa, NULL);
  sigaction(SIGTERM, &sa, NULL);
  sigaction(SIGHUP,  &sa, NULL);
  sigaction(SIGQUIT, &sa, NULL);

  rfbRunEventLoop(rfbScreen,-1,TRUE);

  while(rfbIsActive(rfbScreen)) {
      sleep(1);
  }

  rfbScreenCleanup(rfbScreen);

  system("diskutil unmount /Users/Shared/mnt/z > /dev/null 2>&1");

  rfbLog("Remote done\n");
  return(0);
}
