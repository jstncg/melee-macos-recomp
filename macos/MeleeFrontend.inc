// Native macOS shell. Included by PlatformMacos.mm; game rendering stays in Metal.
#include "Common/FileUtil.h"
#include "AudioCommon/AudioCommon.h"
#include "Common/IniFile.h"
#include "Core/Config/GraphicsSettings.h"
#include "Core/HW/GCPad.h"
#include "Core/HW/SI/SI.h"
#include "Core/HW/SI/SI_Device.h"
#include "InputCommon/ControllerInterface/ControllerInterface.h"
#include <atomic>
extern std::atomic<bool> g_melee_menu_open;

@interface MeleeFrontend : NSObject
@property NSWindow* game;
@property NSPanel* panel;
@property NSMutableDictionary* preferences;
@property NSString* preferencesPath;
@property NSTabView* tabs;
@property NSMutableArray<NSPopUpButton*>* pads;
@property BOOL settingsPaused;
@property BOOL importing;
@property NSTextField* netAddress;
@property NSTextField* netPort;
@property NSTextField* netName;
- (id)initWithGame:(NSWindow*)game;
- (void)home:(id)sender;
- (void)play:(id)sender;
- (void)settings:(id)sender;
@end

@implementation MeleeFrontend
- (NSTextField*)label:(NSString*)text at:(NSRect)rect in:(NSView*)view
{
  NSTextField* label = [NSTextField wrappingLabelWithString:text];
  label.frame = rect; label.textColor = NSColor.labelColor;
  [view addSubview:label]; return label;
}
- (NSButton*)button:(NSString*)title action:(SEL)action at:(NSRect)rect in:(NSView*)view
{
  NSButton* b = [NSButton buttonWithTitle:title target:self action:action];
  b.frame = rect; [view addSubview:b]; return b;
}
- (void)save
{
  if (![self.preferences writeToFile:self.preferencesPath atomically:YES])
  {
    NSAlert* a = [NSAlert new]; a.messageText = @"Could not save settings";
    a.informativeText = self.preferencesPath; [a runModal];
  }
}
- (id)initWithGame:(NSWindow*)game
{
  if (!(self = [super init])) return nil;
  self.game = game;
  self.preferencesPath = [[NSString stringWithUTF8String:File::GetUserPath(D_CONFIG_IDX).c_str()] stringByAppendingPathComponent:@"MeleeFrontend.plist"];
  self.preferences = [NSMutableDictionary dictionaryWithContentsOfFile:self.preferencesPath] ?: [NSMutableDictionary new];
  self.panel = [[NSPanel alloc] initWithContentRect:NSMakeRect(0,0,660,470)
      styleMask:NSWindowStyleMaskTitled backing:NSBackingStoreBuffered defer:NO];
  self.panel.title = @"Melee • Home";
  self.panel.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
  self.panel.backgroundColor = [NSColor colorWithRed:0.065 green:0.075 blue:0.11 alpha:0.96];
  self.panel.hidesOnDeactivate = NO;
  self.panel.collectionBehavior = NSWindowCollectionBehaviorFullScreenAuxiliary;
  NSMenuItem* item = [[NSMenuItem alloc] initWithTitle:@"Melee Home…" action:@selector(home:) keyEquivalent:@"\e"];
  item.keyEquivalentModifierMask = 0; item.target = self;
  [[[NSApp mainMenu] itemAtIndex:0].submenu insertItem:item atIndex:0];
  NSMenuItem* prefs = [[NSMenuItem alloc] initWithTitle:@"Settings…" action:@selector(settings:) keyEquivalent:@","];
  prefs.target = self; [[[NSApp mainMenu] itemAtIndex:0].submenu insertItem:prefs atIndex:1];
  [self home:nil];
  if (const char* error=getenv("MELEE_NETPLAY_ERROR")) {
    NSString* code=@(error); unsetenv("MELEE_NETPLAY_ERROR");
    NSAlert* a=[NSAlert new]; a.messageText=@"Netplay could not complete";
    a.informativeText=[NSString stringWithFormat:@"Returned to Home (code %@). Check the host address, UDP port, and matching build/game data. Details are in logs/app.log.",code];
    [a runModal];
  }
  return self;
}
- (void)position
{
  NSRect r = self.game.frame, p = self.panel.frame;
  [self.panel setFrameOrigin:NSMakePoint(NSMidX(r)-p.size.width/2, NSMidY(r)-p.size.height/2)];
  [self.game addChildWindow:self.panel ordered:NSWindowAbove];
  [self.panel makeKeyAndOrderFront:nil];
}
- (void)home:(id)sender
{
  if (self.settingsPaused) { Core::SetState(Core::System::GetInstance(), Core::State::Running); self.settingsPaused = NO; }
  g_melee_menu_open = true;
  self.panel.title = @"Melee • Home";
  self.panel.contentView = [[NSView alloc] initWithFrame:NSMakeRect(0,0,660,470)];
  NSView* v = self.panel.contentView;
  NSTextField* title = [self label:@"MELEE" at:NSMakeRect(48,335,560,70) in:v];
  title.font = [NSFont systemFontOfSize:54 weight:NSFontWeightHeavy];
  [self label:@"MACOS  /  NATIVE RECOMPILATION" at:NSMakeRect(52,303,550,24) in:v];
  [self button:@"Play" action:@selector(play:) at:NSMakeRect(48,220,260,48) in:v];
  [self button:@"Settings" action:@selector(settings:) at:NSMakeRect(48,159,260,48) in:v];
  [self button:@"Netplay" action:@selector(netplay:) at:NSMakeRect(330,159,260,48) in:v];
  [self button:@"Quit" action:@selector(quit:) at:NSMakeRect(48,98,260,48) in:v];
  [self label:@"Escape opens Home • ⌘, opens Settings\nYour game and memory card stay in this workspace." at:NSMakeRect(52,30,565,48) in:v];
  [self position];
}
- (void)netplay:(id)sender
{
  if (Core::GetState(Core::System::GetInstance()) == Core::State::Running)
  { Core::SetState(Core::System::GetInstance(),Core::State::Paused); self.settingsPaused=YES; }
  g_melee_menu_open=true;
  self.panel.title=@"Melee • Netplay";
  self.panel.contentView=[[NSView alloc] initWithFrame:NSMakeRect(0,0,660,470)];
  NSView* v=self.panel.contentView;
  NSTextField* title=[self label:@"Netplay" at:NSMakeRect(30,385,590,48) in:v];
  title.font=[NSFont systemFontOfSize:32 weight:NSFontWeightBold];
  [self label:@"Direct connection • Fixed input delay • Experimental" at:NSMakeRect(30,345,590,28) in:v];
  NSArray* names=@[@"Nickname",@"Host address",@"UDP port"];
  NSMutableArray* fields=[NSMutableArray new];
  NSArray* values=@[self.preferences[@"net_name"] ?: @"Player",self.preferences[@"net_address"] ?: @"127.0.0.1",self.preferences[@"net_port"] ?: @"2626"];
  for (int i=0;i<3;++i) {
    [self label:names[i] at:NSMakeRect(30,290-i*45,140,28) in:v];
    NSTextField* f=[[NSTextField alloc] initWithFrame:NSMakeRect(185,288-i*45,435,30)];
    f.stringValue=values[i]; [v addSubview:f]; [fields addObject:f];
  }
  self.netName=fields[0]; self.netAddress=fields[1]; self.netPort=fields[2];
  [self label:@"Host starts a room; Join connects to the host’s address. Both players need this same build and game data. On different networks, the host needs UDP port forwarding or a shared VPN. Starting netplay ends the current local game." at:NSMakeRect(30,87,590,100) in:v];
  [self button:@"Back" action:@selector(home:) at:NSMakeRect(30,25,110,38) in:v];
  NSButton* host=[self button:@"Host room" action:@selector(startNetplay:) at:NSMakeRect(290,25,155,38) in:v]; host.tag=0;
  NSButton* join=[self button:@"Join room" action:@selector(startNetplay:) at:NSMakeRect(465,25,155,38) in:v]; join.tag=1;
  [self position];
}
- (void)startNetplay:(NSButton*)sender
{
  NSString* port=self.netPort.stringValue;
  NSString* name=[self.netName.stringValue stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
  NSString* address=[self.netAddress.stringValue stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
  if (!port.length || [port rangeOfCharacterFromSet:NSCharacterSet.decimalDigitCharacterSet.invertedSet].location!=NSNotFound || port.integerValue<1 || port.integerValue>65535 || !name.length || name.length>20 || (sender.tag && !address.length)) {
    NSAlert* a=[NSAlert new]; a.messageText=@"Check connection details"; a.informativeText=@"Use a nickname of 1–20 characters, a UDP port from 1–65535, and a host address when joining."; [a runModal]; return;
  }
  self.preferences[@"net_name"]=name; self.preferences[@"net_address"]=address; self.preferences[@"net_port"]=port; [self save];
  NSDictionary* request=@{@"role":sender.tag ? @"join":@"host",@"address":address,@"port":port,@"nickname":name};
  NSString* path=[self.preferencesPath.stringByDeletingLastPathComponent stringByAppendingPathComponent:@"NetplayRequest.plist"];
  if (![request writeToFile:path atomically:YES]) { NSAlert* a=[NSAlert new]; a.messageText=@"Could not start netplay"; [a runModal]; return; }
  [NSApp terminate:nil];
}
- (void)play:(id)sender
{
  if (self.settingsPaused) { Core::SetState(Core::System::GetInstance(), Core::State::Running); self.settingsPaused = NO; }
  g_melee_menu_open = false;
  [self.game removeChildWindow:self.panel]; [self.panel orderOut:nil];
  [self.game makeKeyAndOrderFront:nil];
}
- (void)quit:(id)sender { [NSApp terminate:nil]; }
- (NSView*)tab:(NSString*)name
{
  NSTabViewItem* t = [[NSTabViewItem alloc] initWithIdentifier:name]; t.label = name;
  t.view = [[NSView alloc] initWithFrame:NSMakeRect(0,0,610,330)]; [self.tabs addTabViewItem:t]; return t.view;
}
- (void)settings:(id)sender
{
  if (Core::GetState(Core::System::GetInstance()) == Core::State::Running)
  { Core::SetState(Core::System::GetInstance(), Core::State::Paused); self.settingsPaused = YES; }
  g_melee_menu_open = true;
  self.panel.title = @"Melee • Settings";
  self.panel.contentView = [[NSView alloc] initWithFrame:NSMakeRect(0,0,660,470)];
  NSView* root = self.panel.contentView;
  self.tabs = [[NSTabView alloc] initWithFrame:NSMakeRect(20,75,620,365)];
  [root addSubview:self.tabs];
  [self button:@"Back" action:@selector(home:) at:NSMakeRect(25,20,115,34) in:root];
  [self button:@"Resume game" action:@selector(play:) at:NSMakeRect(480,20,155,34) in:root];
  NSView* v = [self tab:@"General"];
  [self label:@"Game data" at:NSMakeRect(20,265,550,25) in:v];
  [self label:@"Choose a Melee USA revision 2 ISO, GCM, CISO, or extracted game folder. Imports are checked against this build and take effect next launch." at:NSMakeRect(20,185,560,75) in:v];
  [self button:@"Choose disc image or game folder…" action:@selector(chooseGame:) at:NSMakeRect(20,135,285,35) in:v];
  [self button:@"Show save data" action:@selector(showSaves:) at:NSMakeRect(20,85,285,35) in:v];
  [self label:@"Imports run in the background. Your original disc image and existing memory cards are retained." at:NSMakeRect(20,15,560,58) in:v];
  v = [self tab:@"Video"];
  [self label:@"Internal resolution" at:NSMakeRect(20,265,220,25) in:v];
  NSPopUpButton* scale = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(265,258,280,32) pullsDown:NO];
  [scale addItemsWithTitles:@[@"1× · Native", @"2×", @"3×", @"4×", @"5×", @"6×"]];
  [scale selectItemAtIndex:std::clamp(Config::Get(Config::GFX_EFB_SCALE)-1,0,5)];
  scale.target=self; scale.action=@selector(scale:); [v addSubview:scale];
  NSButton* vs = [NSButton checkboxWithTitle:@"Vertical sync" target:self action:@selector(vsync:)];
  vs.frame=NSMakeRect(20,210,300,30); vs.state=Config::Get(Config::GFX_VSYNC); [v addSubview:vs];
  [self button:@"Toggle fullscreen" action:@selector(fullscreen:) at:NSMakeRect(20,155,250,35) in:v];
  [self label:@"Resolution updates when gameplay resumes. Look for sharper 3D edges; movies and original textures keep their detail.\n\nGameplay remains ≈60 FPS. A 120 Hz display works, but true 120 FPS interpolation is not implemented." at:NSMakeRect(20,30,565,110) in:v];
  v = [self tab:@"Audio"];
  [self label:@"Master volume" at:NSMakeRect(20,260,550,30) in:v];
  NSSlider* volume = [NSSlider sliderWithValue:Config::Get(Config::MAIN_AUDIO_VOLUME) minValue:0 maxValue:100 target:self action:@selector(volume:)];
  volume.frame=NSMakeRect(20,205,530,35); [v addSubview:volume];
  [self label:@"0 = muted  •  100 = full volume\nSaved automatically. Resume the game to hear the new level." at:NSMakeRect(20,110,550,65) in:v];
  v = [self tab:@"Input"];
  self.pads = [NSMutableArray new];
  Common::IniFile ini; ini.Load(File::GetUserPath(D_CONFIG_IDX)+"GCPadNew.ini");
  auto devices = g_controller_interface.GetAllDeviceStrings();
  for (int i=0;i<4;++i)
  {
    [self label:[NSString stringWithFormat:@"Player %d",i+1] at:NSMakeRect(20,267-i*43,100,25) in:v];
    NSPopUpButton* p = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(125,262-i*43,440,32) pullsDown:NO];
    [p addItemsWithTitles:@[@"None", @"Quartz/0/Keyboard & Mouse"]];
    for (const auto& d: devices) if (d.starts_with("SDL/")) [p addItemWithTitle:[NSString stringWithUTF8String:d.c_str()]];
    std::string selected; ini.GetOrCreateSection("GCPad"+std::to_string(i+1))->Get("Device",&selected,"");
    if (!selected.empty()) { NSString* value=[NSString stringWithUTF8String:selected.c_str()]; if (![p itemWithTitle:value]) [p addItemWithTitle:value]; [p selectItemWithTitle:value]; }
    p.tag=i; p.target=self; p.action=@selector(controller:); [v addSubview:p]; [self.pads addObject:p];
  }
  [self button:@"Refresh connected controllers" action:@selector(refresh:) at:NSMakeRect(20,80,330,32) in:v];
  [self label:@"Keyboard stays active for Player 1. PS5: × attack, ○ special, □/△ jump, R1 grab, L2/R2 shield.\nXbox: A attack, B special, X/Y jump, RB grab, LT/RT shield.\nLeft stick / D-pad move • Right stick C-stick • Options/Menu starts." at:NSMakeRect(20,5,560,70) in:v];
  v = [self tab:@"Gameplay"];
  [self label:@"Original Melee rules and timing" at:NSMakeRect(20,260,550,30) in:v];
  [self label:@"Set stocks, time, items, and difficulty in Melee’s own menus. Settings pause gameplay; Home lets the game run with controller input blocked. Escape returns to Home.\n\nSave-state commands remain available in the macOS States menu. Memory-card saves persist automatically." at:NSMakeRect(20,65,555,180) in:v];
  v = [self tab:@"Cheats"];
  [self label:@"Cheat support is not enabled" at:NSMakeRect(20,260,550,30) in:v];
  [self label:@"This native build uses a pinned recompiled executable. Arbitrary code patches can invalidate it. A verified native cheat implementation is needed before toggles can safely affect the game.\n\nNo cheat codes are applied." at:NSMakeRect(20,75,555,160) in:v];
  [self position];
}
- (void)volume:(NSSlider*)sender { Config::SetCurrent(Config::MAIN_AUDIO_VOLUME,sender.intValue); AudioCommon::UpdateSoundStream(Core::System::GetInstance()); self.preferences[@"volume"]=@(sender.intValue); [self save]; }
- (void)scale:(NSPopUpButton*)sender { int value=(int)sender.indexOfSelectedItem+1; Config::SetCurrent(Config::GFX_EFB_SCALE,value); self.preferences[@"scale"]=@(value); [self save]; }
- (void)vsync:(NSButton*)sender { bool value=sender.state==NSControlStateValueOn; Config::SetCurrent(Config::GFX_VSYNC,value); self.preferences[@"vsync"]=@(value); [self save]; }
- (void)fullscreen:(id)sender { [self.game toggleFullScreen:nil]; }
- (void)showSaves:(id)sender { [[NSWorkspace sharedWorkspace] openURL:[NSURL fileURLWithPath:[self.preferencesPath stringByDeletingLastPathComponent].stringByDeletingLastPathComponent]]; }
- (void)refresh:(id)sender { g_controller_interface.RefreshDevices(); [self settings:nil]; [self.tabs selectTabViewItemAtIndex:3]; }
- (void)controller:(NSPopUpButton*)sender
{
  Common::IniFile ini; const auto path=File::GetUserPath(D_CONFIG_IDX)+"GCPadNew.ini"; ini.Load(path);
  auto* s=ini.GetOrCreateSection("GCPad"+std::to_string(sender.tag+1));
  std::string device=sender.titleOfSelectedItem.UTF8String;
  if (device=="None") { ini.DeleteSection("GCPad"+std::to_string(sender.tag+1)); ini.GetOrCreateSection("GCPad"+std::to_string(sender.tag+1))->Set("Device", std::string{}); }
  else
  {
    s->Set("Device",device);
    const bool keyboard=device.starts_with("Quartz/");
    const char* keys[][3] = {
      {"Buttons/A","J","`Button A`"},{"Buttons/B","K","`Button B`"},{"Buttons/X","Space","`Button X`"},{"Buttons/Y","U","`Button Y`"},
      {"Buttons/Z","O","`Shoulder R`"},{"Buttons/Start","Return","Start"},
      {"Main Stick/Up","W","`Left Y+` | `Pad N`"},{"Main Stick/Down","S","`Left Y-` | `Pad S`"},{"Main Stick/Left","A","`Left X-` | `Pad W`"},{"Main Stick/Right","D","`Left X+` | `Pad E`"},
      {"C-Stick/Up","Up","`Right Y+`"},{"C-Stick/Down","Down","`Right Y-`"},{"C-Stick/Left","Left","`Right X-`"},{"C-Stick/Right","Right","`Right X+`"},
      {"Triggers/L","Q","`Trigger L`"},{"Triggers/R","E","`Trigger R`"},{"Triggers/L-Analog","Q","`Trigger L`"},{"Triggers/R-Analog","E","`Trigger R`"},
      {"D-Pad/Up","T",""},{"D-Pad/Down","G",""},{"D-Pad/Left","F",""},{"D-Pad/Right","H",""},
      {"Rumble/Motor","","`Motor L` | `Motor R`"}};
    for (const auto& k:keys)
    {
      std::string expression = k[keyboard?1:2];
      if (!keyboard && sender.tag==0 && *k[1])
        expression += (expression.empty() ? "" : " | ") + std::string("`Quartz/0/Keyboard & Mouse:") + k[1] + "`";
      s->Set(k[0],expression);
    }
    s->Set("Main Stick/Dead Zone",10.0); s->Set("C-Stick/Dead Zone",10.0);
  }
  if (ini.Save(path))
  {
    Pad::LoadConfig();
    auto type=device=="None" ? SerialInterface::SIDEVICE_NONE : SerialInterface::SIDEVICE_GC_CONTROLLER;
    Config::SetBase(Config::GetInfoForSIDevice((int)sender.tag),type);
    Core::System::GetInstance().GetSerialInterface().ChangeDevice(type,(int)sender.tag);
  }
}
- (void)chooseGame:(id)sender
{
  if (self.importing) return;
  NSOpenPanel* p=[NSOpenPanel openPanel]; p.canChooseDirectories=YES; p.canChooseFiles=YES; p.allowsMultipleSelection=NO;
  if ([p runModal]!=NSModalResponseOK) return;
  BOOL directory=NO; [[NSFileManager defaultManager] fileExistsAtPath:p.URL.path isDirectory:&directory];
  if (!directory)
  {
    self.importing=YES;
    NSString* source=p.URL.path;
    NSString* workspace=@(getenv("MELEE_WORKSPACE") ?: "");
    [sender setEnabled:NO]; [sender setTitle:@"Importing…"];
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0), ^{
      NSTask* task=[NSTask new];
      task.executableURL=[NSURL fileURLWithPath:@"/opt/homebrew/bin/python3"];
      task.arguments=@[[workspace stringByAppendingPathComponent:@"scripts/import_game.py"],source];
      NSPipe* pipe=[NSPipe pipe]; task.standardOutput=pipe; task.standardError=pipe;
      NSError* error=nil; NSString* result=@""; BOOL launched=[task launchAndReturnError:&error];
      if (launched) { result=[[NSString alloc] initWithData:[pipe.fileHandleForReading readDataToEndOfFile] encoding:NSUTF8StringEncoding] ?: @""; [task waitUntilExit]; }
      dispatch_async(dispatch_get_main_queue(), ^{
        self.importing=NO; [sender setEnabled:YES]; [sender setTitle:@"Choose disc image or game folder…"];
        NSAlert* a=[NSAlert new];
        NSRange marker=[result rangeOfString:@"IMPORTED_GAME=" options:NSBackwardsSearch];
        if (launched && task.terminationStatus==0 && marker.location!=NSNotFound)
        {
          self.preferences[@"game_path"]=[[result substringFromIndex:NSMaxRange(marker)] stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
          self.preferences[@"disc_image"]=source; [self save];
          a.messageText=@"Disc imported"; a.informativeText=@"The verified game data will be used next launch. Your saves are unchanged.";
        }
        else { a.messageText=@"Disc import failed"; a.informativeText=error.localizedDescription ?: [result substringFromIndex:result.length>1200?result.length-1200:0]; }
        [a runModal];
      });
    });
    return;
  }
  NSString* candidate=[p.URL.path stringByAppendingPathComponent:@"sys/main.dol"];
  NSString* current=[@(getenv("MELEE_WORKSPACE") ?: "") stringByAppendingPathComponent:@"private/GALE01r2/sys/main.dol"];
  NSData* data=[NSData dataWithContentsOfFile:candidate];
  if (!data || ![data isEqualToData:[NSData dataWithContentsOfFile:current]] || ![[NSFileManager defaultManager] fileExistsAtPath:[p.URL.path stringByAppendingPathComponent:@"files"]])
  { NSAlert* a=[NSAlert new]; a.messageText=@"Unsupported game data"; a.informativeText=@"Select extracted GALE01 USA revision 2 data matching this build."; [a runModal]; return; }
  self.preferences[@"game_path"]=p.URL.path; [self save];
}
@end

// Runtime calls this after its defaults are installed, before game/audio/video boot.
extern "C" void MeleeApplyMediaPreferences()
{
  @autoreleasepool {
    NSString* path=[[NSString stringWithUTF8String:File::GetUserPath(D_CONFIG_IDX).c_str()] stringByAppendingPathComponent:@"MeleeFrontend.plist"];
    NSDictionary* prefs=[NSDictionary dictionaryWithContentsOfFile:path];
    if (prefs[@"volume"]) Config::SetCurrent(Config::MAIN_AUDIO_VOLUME,std::clamp([prefs[@"volume"] intValue],0,100));
    if (prefs[@"scale"]) Config::SetCurrent(Config::GFX_EFB_SCALE,std::clamp([prefs[@"scale"] intValue],1,6));
    if (prefs[@"vsync"]) Config::SetCurrent(Config::GFX_VSYNC,[prefs[@"vsync"] boolValue]);
  }
}
