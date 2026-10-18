// Direct producer for an already installed GhaustCam Camera Extension.
#import <Foundation/Foundation.h>
#import <CoreMediaIO/CoreMediaIO.h>
#import <CoreVideo/CoreVideo.h>
#import <mach/mach_time.h>
#include <string.h>
#include <stdlib.h>

typedef struct { CMIODeviceID device; CMIOStreamID stream; CMSimpleQueueRef queue;
 CVPixelBufferPoolRef pool; CMVideoFormatDescriptionRef format; int width,height; } Sink;
static CMIOObjectPropertyAddress prop(UInt32 sel) {
 return (CMIOObjectPropertyAddress){sel,kCMIOObjectPropertyScopeGlobal,kCMIOObjectPropertyElementMain};
}
static UInt32 *objects(CMIOObjectID object, UInt32 sel, UInt32 *count) {
 CMIOObjectPropertyAddress p=prop(sel); UInt32 size=0,used=0;*count=0;
 if(CMIOObjectGetPropertyDataSize(object,&p,0,NULL,&size))return NULL;
 UInt32 *items=calloc(1,size);if(!items)return NULL;
 if(CMIOObjectGetPropertyData(object,&p,0,NULL,size,&used,items)){free(items);return NULL;}
 *count=used/sizeof(UInt32);return items;
}
static CMIODeviceID find_device(void) {
 CMIOObjectPropertyAddress p=prop(kCMIOHardwarePropertyAllowScreenCaptureDevices);UInt32 yes=1;
 CMIOObjectSetPropertyData(kCMIOObjectSystemObject,&p,0,NULL,4,&yes);
 UInt32 count=0;UInt32 *devices=objects(kCMIOObjectSystemObject,kCMIOHardwarePropertyDevices,&count);
 CMIODeviceID found=0;p=prop('gcnm');
 for(UInt32 i=0;i<count;i++){
  // GhaustCam recreates its device with a new UUID when renamed.
  if(CMIOObjectHasProperty(devices[i],&p))found=devices[i];
 }
 free(devices);return found;
}
int eye_sink_available(void){return find_device()!=0;}
int eye_sink_rename(const char *name) {
 CMIODeviceID d=find_device();if(!d)return -1;
 CFStringRef value=CFStringCreateWithCString(NULL,name,kCFStringEncodingUTF8);if(!value)return -2;
 CMIOObjectPropertyAddress p=prop('gcnm');
 OSStatus err=CMIOObjectSetPropertyData(d,&p,0,NULL,sizeof(value),&value);CFRelease(value);return err;
}
void eye_sink_close(void *handle){Sink *s=handle;if(!s)return;
 if(s->stream)CMIODeviceStopStream(s->device,s->stream);
 if(s->queue)CFRelease(s->queue);if(s->format)CFRelease(s->format);if(s->pool)CFRelease(s->pool);free(s);
}
static void changed(CMIOStreamID stream,void *token,void *refcon){}
void *eye_sink_open(int width,int height,int *error){@autoreleasepool{
 NSDictionary *attrs=nil; *error=-1;Sink *s=calloc(1,sizeof(Sink));if(!s)return NULL;s->device=find_device();s->width=width;s->height=height;
 if(!s->device)goto fail;
 UInt32 count=0;UInt32 *streams=objects(s->device,kCMIODevicePropertyStreams,&count);
 for(UInt32 i=0;i<count;i++){UInt32 direction=99,used=0;CMIOObjectPropertyAddress p=prop(kCMIOStreamPropertyDirection);
 if(!CMIOObjectGetPropertyData(streams[i],&p,0,NULL,4,&used,&direction)&&direction==0)s->stream=streams[i];}
 free(streams);if(!s->stream)goto fail;
 *error=CMIOStreamCopyBufferQueue(s->stream,changed,NULL,&s->queue);if(*error)goto fail;
 attrs=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_32BGRA),
 (id)kCVPixelBufferWidthKey:@(width),(id)kCVPixelBufferHeightKey:@(height),(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
 *error=CVPixelBufferPoolCreate(NULL,NULL,(__bridge CFDictionaryRef)attrs,&s->pool);if(*error)goto fail;
 *error=CMVideoFormatDescriptionCreate(NULL,kCVPixelFormatType_32BGRA,width,height,NULL,&s->format);if(*error)goto fail;
 *error=CMIODeviceStartStream(s->device,s->stream);if(*error)goto fail;return s;
 fail:eye_sink_close(s);return NULL;
}}
int eye_sink_send(void *handle,const unsigned char *bytes,int stride){@autoreleasepool{
 Sink *s=handle;if(!s||stride<s->width*4)return -1;
 if(CMSimpleQueueGetCount(s->queue)>=1)return 1;
 CVPixelBufferRef buffer=NULL;NSDictionary *aux=@{(id)kCVPixelBufferPoolAllocationThresholdKey:@6};
 int err=CVPixelBufferPoolCreatePixelBufferWithAuxAttributes(NULL,s->pool,(__bridge CFDictionaryRef)aux,&buffer);if(err)return err;
 CVPixelBufferLockBaseAddress(buffer,0);unsigned char *dst=CVPixelBufferGetBaseAddress(buffer);size_t outStride=CVPixelBufferGetBytesPerRow(buffer);
 for(int y=0;y<s->height;y++)memcpy(dst+y*outStride,bytes+y*stride,s->width*4);
 CVPixelBufferUnlockBaseAddress(buffer,0);
 CMSampleTimingInfo timing={.duration=CMTimeMake(1,30),.presentationTimeStamp=CMClockGetTime(CMClockGetHostTimeClock()),.decodeTimeStamp=kCMTimeInvalid};
 CMSampleBufferRef sample=NULL;err=CMSampleBufferCreateForImageBuffer(NULL,buffer,true,NULL,NULL,s->format,&timing,&sample);CVPixelBufferRelease(buffer);
 if(err)return err;err=CMSimpleQueueEnqueue(s->queue,sample);if(err)CFRelease(sample);return err;
}}
