#!/usr/bin/env python2
import numpy as np
import cv2
import time
import pdb
from feedback_ext import *

# Webcam types:
IN_BUILT_CAM = 0
C920_CAM = 2

# Color Filter: BGR Values
# THESE VALUES ARE ALLOWED
COLOR_FILTER_low = np.array([0, 0, 0])
COLOR_FILTER_high = np.array([255, 255, 180])

# Ball position tracking
ORIGIN = np.array([270.0,90.0])
X_RANGE = 520
Z_RANGE = 460

class Webcam_capture():
    
    def __init__(self):
        # Setup capture
        self.cap = cv2.VideoCapture(C920_CAM)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Buffer of 1 to throw away old frames
        # self.vid = cv2.VideoWriter('Laser_Test_Video.mp4', 0x7634706d, 2, (640, 480)) # mp4

        ## Blob detection:
        # Setup SimpleBlobDetector parameters
        params = cv2.SimpleBlobDetector_Params()
        # Change thresholds
        params.minThreshold = 0
        params.maxThreshold = 500
        # Filter by center of blob color
        params.filterByColor = False
        # params.blobColor = 0 # Dark center
        # Filter by Area.
        params.filterByArea = True
        params.minArea = 1
        params.maxArea = 30
        # Filter by Circularity
        params.filterByCircularity = False
        # params.minCircularity = 0.2
        # Filter by Convexity
        params.filterByConvexity = False
        # params.minConvexity = 0.5
        # Filter by Inertia
        params.filterByInertia = False
        # params.minInertiaRatio = 0.4
        # params.maxInertiaRatio = 0.4

        # Set up the detector
        self.detector = cv2.SimpleBlobDetector_create(params)

        # Flag to show kinect image stream
        self.show_img = True
        # Flag to show position of keypoints
        self.show_pos = False
        
        self.laser_pos = ORIGIN
        self.laser_vel = np.array([0.0,0.0])

        # Init webcam and let it adjust exposure for 2 seconds
        self.prev_time = time.time()
        start = time.time()
        elapsed = time.time() - start
        while (elapsed < 1):
            pos = self.get_laser_state()
            print("laser_position (X,Z): ", pos)
            elapsed = time.time() - start


    def get_laser_state(self, h_feedback=0):
        # Capture frame        
        self.cap.grab() # Throw previous frame in buffer
        ret, frame = self.cap.read()
        if(not ret):
            print("No image stream from webcam")
            return
        
        # Cut image:
        color_img = frame[21:, 92:608, :]
        # Color mask: blue
        mask = cv2.inRange(color_img, COLOR_FILTER_low, COLOR_FILTER_high)
        color_img = cv2.bitwise_and(color_img,color_img, mask=mask) # AND with main image
        # Detect blobs
        keypoints = self.detector.detect(color_img)
        # color_img = frame
        # Debug: Uncomment to see mask:
        # color_img = mask

        num_keyps = len(keypoints)
        im_with_keypoints = color_img
        # if(num_keyps == 1):
        #     keyp = keypoints
        #     self.laser_pos = np.array([keypoints[0].pt[0], keypoints[0].pt[1]])
        #     if(self.show_img):
        #         # Draw keypoints
        #         im_with_keypoints = cv2.drawKeypoints(color_img, keyp, np.array([]), (0,0,255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)            
        if(num_keyps >= 1):
            # Get smallest size keypoint
            index = np.argmax(keyp.size for keyp in keypoints)
            keyp = [keypoints[index]]
            
            # Time interval (for velocity calculation)
            dt = time.time()- self.prev_time
            # print("Time interval:", dt)
            self.prev_time = time.time()
            
            laser_pos_now = np.array([keypoints[index].pt[0], keypoints[index].pt[1]])

            #KF: Curently removed
            self.laser_vel = (laser_pos_now - self.laser_pos)/dt
            self.laser_pos = laser_pos_now
            # meas = np.array([[laser_pos_now[0]],[laser_pos_now[1]]])
            # est_state = kalman.correct(meas)
            # self.laser_pos[0] = est_state[0]
            # self.laser_pos[1] = est_state[1]
            # self.laser_pos[0] = est_state[2]
            # self.laser_pos[1] = est_state[3]
            # kalman.predict() # predict next

            
            if(self.show_img):
                # Draw keypoints
                im_with_keypoints = cv2.drawKeypoints(color_img, keyp, np.array([]), (0,0,255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
                # pt1 = (int(keypoints[index].pt[0]),int(keypoints[index].pt[1]))
                # if (h_feedback < 5 and h_feedback > 0):
                #     if (h_feedback == H_UP):
                #         pt2 = (int(keypoints[index].pt[0]),int(keypoints[index].pt[1]-50))
                #     elif (h_feedback == H_DOWN):
                #         pt2 = (int(keypoints[index].pt[0]),int(keypoints[index].pt[1]+50))
                #     elif (h_feedback == H_LEFT):
                #         pt2 = (int(keypoints[index].pt[0]-50),int(keypoints[index].pt[1]))
                #     elif (h_feedback == H_RIGHT):
                #         pt2 = (int(keypoints[index].pt[0]+50),int(keypoints[index].pt[1]))
                #     im_with_keypoints = cv2.arrowedLine(color_img, pt1, pt2, (0,0,200), 8)

        # Optional: Display stuff
        if(self.show_img):
            # Show keypoints
            cv2.imshow("Keypoints", im_with_keypoints)
            # self.vid.write(im_with_keypoints)
        if(self.show_pos):
            print("laser_position (X,Z): ", str(self.laser_pos))
            # print("laser_velocity (X,Z): ", str(self.laser_vel))
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.show_img = False
            self.show_pos = False
            # self.vid.release()
            cv2.destroyAllWindows()

        # Normalize and return:
        laser_p = np.array([0.0,0.0])
        laser_p[0] = (self.laser_pos[0] - ORIGIN[0])/X_RANGE  # Laser x position
        laser_p[1] = (ORIGIN[1] - self.laser_pos[1])/Z_RANGE  # Laser z position
        # laser_v = np.array([0.0,0.0])
        # laser_v[0] = self.laser_vel[0]/X_RANGE  # Laser x velocity
        # laser_v[1] = -self.laser_vel[1]/Z_RANGE  # Laser z velocity

        return laser_p