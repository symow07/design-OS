import numpy as np
import cv2

def lin(a):
 a=np.asarray(a,dtype=float)/255
 return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)

def enc(a):
 a=np.clip(a,0,1)
 return np.clip(np.round(255*np.where(a<=.0031308,12.92*a,1.055*a**(1/2.4)-.055)),0,255).astype(np.uint8)

def lab(a):
 xyz=lin(a)@np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]]).T
 v=xyz/np.array([.95047,1,1.08883]);f=np.where(v>(6/29)**3,np.cbrt(v),v/(3*(6/29)**2)+4/29)
 return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],-1)

def de(a,b):
 l1,a1,b1=np.moveaxis(a,-1,0);l2,a2,b2=np.moveaxis(b,-1,0)
 c1=np.hypot(a1,b1);c2=np.hypot(a2,b2);cm=(c1+c2)/2;g=.5*(1-np.sqrt(cm**7/(cm**7+25**7)))
 ap1=(1+g)*a1;ap2=(1+g)*a2;cp1=np.hypot(ap1,b1);cp2=np.hypot(ap2,b2)
 h1=np.degrees(np.arctan2(b1,ap1))%360;h2=np.degrees(np.arctan2(b2,ap2))%360
 dh=(h2-h1+180)%360-180;dh=np.where(cp1*cp2==0,0,dh)
 dH=2*np.sqrt(cp1*cp2)*np.sin(np.radians(dh/2));dl=l2-l1;dc=cp2-cp1;lm=(l1+l2)/2;cm=(cp1+cp2)/2
 hm=np.where(cp1*cp2==0,h1+h2,np.where(np.abs(h1-h2)<=180,(h1+h2)/2,np.where(h1+h2<360,(h1+h2+360)/2,(h1+h2-360)/2)))
 t=1-.17*np.cos(np.radians(hm-30))+.24*np.cos(np.radians(2*hm))+.32*np.cos(np.radians(3*hm+6))-.20*np.cos(np.radians(4*hm-63))
 sl=1+.015*(lm-50)**2/np.sqrt(20+(lm-50)**2);sc=1+.045*cm;sh=1+.015*cm*t
 rt=-2*np.sqrt(cm**7/(cm**7+25**7))*np.sin(np.radians(60*np.exp(-((hm-275)/25)**2)))
 return np.sqrt(np.maximum((dl/sl)**2+(dc/sc)**2+(dH/sh)**2+rt*(dc/sc)*(dH/sh),0))

def resample(rgba,mx,my):
 a=rgba[:,:,3:4].astype(float)/255;v=np.dstack([lin(rgba[:,:,:3])*a,a]).astype(np.float32)
 z=cv2.remap(v,mx.astype(np.float32),my.astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT);a=np.clip(z[:,:,3:4],0,1)
 rgb=enc(z[:,:,:3]/np.maximum(a,1e-9));rgb[a[:,:,0]<=0]=0
 return np.dstack([rgb,np.round(a[:,:,0]*255).astype(np.uint8)])
