// iOS Simulator Skill Duo backend. Mechanism research: artemnovichkov/hinge and skarol/duoctl.
// Private simulator interfaces: replace when supported headless APIs provide equivalent readback.
#import <Foundation/Foundation.h>
#import <mach/mach_time.h>
#import <unistd.h>
#import <math.h>
typedef CFTypeRef HIDClient;
typedef CFTypeRef HIDEvent;
extern HIDClient IOHIDEventSystemClientCreateWithType(CFAllocatorRef, int, CFDictionaryRef);
extern void IOHIDEventSystemClientDispatchEvent(HIDClient, HIDEvent);
extern CFDataRef IOCFSerialize(CFTypeRef, CFOptionFlags);
extern HIDEvent IOHIDEventCreateVendorDefinedEvent(CFAllocatorRef, uint64_t, uint32_t, uint32_t, uint32_t, const uint8_t *, CFIndex, uint32_t);
@interface NSObject (XCMotion)
+ (BOOL)isAvailable;
- (void)startAngleUpdatesToQueue:(NSOperationQueue *)queue handler:(void (^)(id))handler;
- (void)stopAngleUpdates;
- (float)angleDegrees;
@end
static int readAngle(void) {
    Class cls = NSClassFromString(@"CMAngleManager");
    if (!cls || ![cls isAvailable]) return 69;
    id manager = [cls new];
    dispatch_semaphore_t ready = dispatch_semaphore_create(0);
    __block double value = NAN;
    [manager startAngleUpdatesToQueue:[NSOperationQueue new] handler:^(id sample) {
        value = [sample angleDegrees];
        dispatch_semaphore_signal(ready);
    }];
    long timeout = dispatch_semaphore_wait(ready, dispatch_time(DISPATCH_TIME_NOW, 2 * NSEC_PER_SEC));
    [manager stopAngleUpdates];
    if (timeout || !isfinite(value)) return 70;
    printf("%.3f\n", value);
    return 0;
}
static BOOL sendValue(HIDClient client, NSString *source, NSString *kind, id value) {
    for (NSString *provider in @[@"com.apple.Virtualization", @"com.apple.Virtualization.VirtualMachines"]) {
        NSDictionary *payload = @{@"provider":provider, @"source":source, @"type":kind, @"value":value};
        CFDataRef data = IOCFSerialize((__bridge CFTypeRef)payload, 1);
        if (!data) return NO;
        HIDEvent event = IOHIDEventCreateVendorDefinedEvent(NULL, mach_absolute_time(), 0xFF61, 0x5B, 0, CFDataGetBytePtr(data), CFDataGetLength(data), 0);
        CFRelease(data);
        if (!event) return NO;
        IOHIDEventSystemClientDispatchEvent(client, event);
        CFRelease(event);
    }
    return YES;
}
int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc == 2 && !strcmp(argv[1], "read")) return readAngle();
        if (argc != 3 && argc != 4) return 64;
        NSString *operation = @(argv[1]);
        BOOL hinge = [operation isEqualToString:@"hinge"];
        double target = 0, initial = 0;
        if (hinge) {
            if (argc != 4) return 64;
            char *end;
            initial = strtod(argv[2], &end);
            if (*end || !isfinite(initial) || initial < 0 || initial > 180) return 64;
            target = strtod(argv[3], &end);
            if (*end || !isfinite(target) || target < 0 || target > 180) return 64;
        } else if (![operation isEqualToString:@"orientation"] || argc != 3 || ![@[@"portrait", @"pud", @"landscape-left", @"landscape-right"] containsObject:@(argv[2])]) return 64;
        HIDClient client = IOHIDEventSystemClientCreateWithType(NULL, 4, NULL);
        if (!client) return 69;
        BOOL ok = YES;
        // A short continuous transition lets the runtime hand over between displays.
        for (int step = 1; step <= (hinge ? 24 : 1); step++) {
            id value = hinge ? (id)@(initial + (target - initial) * step / 24.0) : (id)@(argv[2]);
            ok = sendValue(client, hinge ? @"hinge-slider-control" : @"orientation-picker-control", hinge ? @"range" : @"enum", value);
            if (!ok) break;
            if (hinge) usleep(20000);
        }
        usleep(100000);
        CFRelease(client);
        return ok ? 0 : 70;
    }
}
