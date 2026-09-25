# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

'''
Template matching helpers.

This module contains the pure image-matching logic used to locate a recorded template image
within a screenshot.  It is deliberately free of any DUT, RPC, or Params dependencies so that
it can be used both by the live Scenario class (see core/app_scenario.py) and by offline tools
that only have image data to work with (e.g. utilities/open_source/perf_process.py).

The Scenario class keeps thin wrappers (_get_point_by_template / _check_by_template) that build
a TemplateMatcher from its runtime configuration and delegate here.
'''

import logging
import os

import cv2 as cv
from PIL import Image
import imutils


class TemplateMatcher(object):
    '''
    Locates a template image within a screenshot using edge-based template matching.

    All tuning knobs mirror the historical template-matching class variables from Scenario and
    keep the same defaults, so behavior is unchanged when driven from a live scenario run.
    Screenshots and templates are numpy (BGR) images; templates are supplied as file paths so
    their authoring DPI can be read for DPI standardization.
    '''

    # Template matching method
    default_template_method = cv.TM_SQDIFF_NORMED

    def __init__(self,
                 json_parent_dir="",
                 device_scale=1.0,
                 threshold=0.70,
                 scale_factors=None,
                 edge_detect=True,
                 edge_detect_thresholds=None,
                 edge_blur=True,
                 edge_blur_kernel=7,
                 upscale=1.0,
                 template_edge_crop=True,
                 template_edge_crop_amount=5,
                 standardize_dpi=True,
                 dialation=True,
                 dialation_kernel=(3, 3),
                 debug_dir=None,
                 output_images=False):
        self.json_parent_dir = json_parent_dir              # Directory where template images are stored
        self.device_scale = device_scale                    # Device display scale factor (1.0 == 96 DPI)
        self.default_threshold = threshold                   # Threshold for template matching
        self.default_scale = scale_factors if scale_factors is not None else [1.0]  # Scale factors to check
        self.edge_detect = edge_detect                       # Enable edge detection
        self.edge_detect_thresholds = edge_detect_thresholds if edge_detect_thresholds is not None else [5, 30]
        self.edge_blur = edge_blur                           # Enable edge blur
        self.edge_blur_kernel = edge_blur_kernel             # Kernel size for edge blur
        self.upscale = upscale                               # Upscale the template and screenshot by this factor
        self.template_edge_crop = template_edge_crop         # Crop the edges of the template in for blur space
        self.template_edge_crop_amount = template_edge_crop_amount  # Pixels to crop from template edges
        self.standardize_dpi = standardize_dpi               # Standardize template DPI to the device DPI
        self.dialation = dialation                           # Apply dilation after edge detection and before blur
        self.dialation_kernel = dialation_kernel             # Dilation kernel size
        self.debug_dir = debug_dir                           # If set, debug images are written here
        self.output_images = output_images                   # Output intermediate images for debugging

    # Save a debug image, if a debug directory has been configured.
    def _save_screen(self, filename, img):
        if not self.debug_dir:
            return
        os.makedirs(self.debug_dir, exist_ok=True)
        save_path = os.path.join(self.debug_dir, filename)
        if len(img.shape) == 3:  # Has 3 elements for color images, only 2 for grayscale.
            rgb_image = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        else:
            # Don't try to convert grayscale images
            rgb_image = img
        Image.fromarray(rgb_image).save(save_path)  # Convert for PIL

    # Get the point of the template in the screenshot.
    # Returns (point, confidence, next_best_confidence), where point is False if no match is above threshold.
    def get_point(self, template, screenshot, threshold=None, method=default_template_method, scale_factors=None, offsets=(0.5, 0.5), edge_detect_thresholds=None):
        # Check if the threshold is provided
        if threshold is None:
            threshold = self.default_threshold

        if scale_factors is None:
            scale_factors = self.default_scale

        if not edge_detect_thresholds:
            edge_detect_thresholds = self.edge_detect_thresholds
        logging.debug(f"Using edge detect thresholds: {edge_detect_thresholds}")

        # Use the provided screenshot (numpy array)
        screen_img = screenshot
        screen_img = cv.cvtColor(screen_img, cv.COLOR_BGR2GRAY)

        if self.upscale != 1.0:
            screen_img = cv.resize(screen_img, (int(screen_img.shape[1] * (self.upscale)), int(screen_img.shape[0] * (self.upscale))), interpolation= cv.INTER_LINEAR)

        screen_gray_img = screen_img

        # Load the recorded template in opencv
        if isinstance(template, str):
            # logging.debug("Loading template: " + str(template))
            # Load the template from a file if a string is provided
            template_img = cv.imread(os.path.join(self.json_parent_dir, template))
            template_img = cv.cvtColor(template_img, cv.COLOR_BGR2GRAY)
        else:
            # Use the provided template if it is a numpy array already
            raise Exception("Template must be file path in order to read dpi! Unable to use preloaded template.")

        # Check if the template and screenshot are valid and that the template is smaller than the screenshot
        assert template_img is not None, "Template not found"
        assert screen_img is not None, "Screenshot not found"

        if self.upscale != 1.0:
            template_img = cv.resize(template_img, (int(template_img.shape[1] * (self.upscale)), int(template_img.shape[0] * (self.upscale))), interpolation= cv.INTER_LINEAR)

        # Default the DPI comparison values in case DPI standardization is disabled.
        template_dpi = 0
        device_dpi = 0

        if self.standardize_dpi:
            # Adjust the scale of the template to match the device Windows scaling
            template_dpi = int(Image.open(os.path.join(self.json_parent_dir, template)).info['dpi'][0])
            if (template_dpi == 0):
                logging.warning(f"Template DPI is 0, defaulting to 96")
                template_dpi = 96
            factor = round(template_dpi / 24)
            template_dpi = factor * 24
            device_dpi = int(self.device_scale * 96)
            logging.debug(f"DPI - Template: {template_dpi}, Device: {device_dpi}")
            if template_dpi > device_dpi:
                scale_factor = template_dpi / device_dpi
                logging.debug(f"Scaling screen capture by {scale_factor:.2f} to match template DPI")
                screen_img = cv.resize(screen_img, (int(screen_img.shape[1] * scale_factor), int(screen_img.shape[0] * scale_factor)), interpolation= cv.INTER_LINEAR)
            elif template_dpi < device_dpi:
                scale_factor = device_dpi / template_dpi
                logging.debug(f"Scaling template by {scale_factor:.2f} to match device DPI")
                template_img = cv.resize(template_img, (int(template_img.shape[1] * scale_factor), int(template_img.shape[0] * scale_factor)), interpolation= cv.INTER_LINEAR)
            else:
                # They are the same DPI and no need to resize
                pass

            template_resize_img = template_img

        if self.edge_blur:
            screen_img = cv.GaussianBlur(screen_img,(3, 3),0)

        # Adjust the screenshot (outside of loop to avoid multiple adjustments)
        if self.edge_detect:
            screen_img = cv.Canny(screen_img, edge_detect_thresholds[0], edge_detect_thresholds[1])
            screen_edge_img = screen_img

        # Apply dilation
        if self.dialation:
            kernel = cv.getStructuringElement(cv.MORPH_RECT, self.dialation_kernel)
            screen_img = cv.dilate(screen_img, kernel, iterations=1)

        if self.edge_blur:
            screen_img = cv.GaussianBlur(screen_img,( self.edge_blur_kernel, self.edge_blur_kernel),0)

        # Make sure the scale factors are in a list even if only one is provided
        if not isinstance(scale_factors, list):
            scale_factors = [scale_factors]

        best_match = (False, 0)
        next_best_match_val = 0
        # Loop through the scaled templates and find the best match
        for scale in scale_factors:
            resized_template = imutils.resize(template_img, width=int(template_img.shape[1] * scale))
            h_screen = screen_img.shape[0]
            w_screen = screen_img.shape[1]
            h_template = int(template_img.shape[0] * scale)
            w_template = int(template_img.shape[1] * scale)
            if (h_screen < h_template) or (w_screen < w_template):
                # Skip loop, template is larger than screenshot
                continue

            # Crop the edges of the template
            if self.template_edge_crop:
                resized_template = resized_template[self.template_edge_crop_amount:-self.template_edge_crop_amount, self.template_edge_crop_amount:-self.template_edge_crop_amount]
                h_template -= (self.template_edge_crop_amount * 2)
                w_template -= (self.template_edge_crop_amount * 2)

            # Convert the offsets to pixel values in the template
            pixel_offsets = (float(offsets[0]) * resized_template.shape[1], float(offsets[1]) * resized_template.shape[0])

            # Blur Edge detection images
            if self.edge_blur:
                resized_template = cv.GaussianBlur(resized_template, (3, 3), 0)

            # Edge detection
            if self.edge_detect:
                resized_template = cv.Canny(resized_template, edge_detect_thresholds[0], edge_detect_thresholds[1])
                resized_edge_template = resized_template

            # Apply dilation
            if self.dialation:
                kernel = cv.getStructuringElement(cv.MORPH_RECT, self.dialation_kernel)
                resized_template = cv.dilate(resized_template, kernel, iterations=1)

            # Blur Edge detection images
            if self.edge_blur:
                resized_template = cv.GaussianBlur(resized_template, (self.edge_blur_kernel, self.edge_blur_kernel), 0)

            if self.output_images:
                template_basename = os.path.basename(template)
                self._save_screen("scaled_template_" + str(scale) + "_" + str(template_basename), resized_template)
                self._save_screen("capture_img_" + str(template_basename), screen_img)

            # Apply template matching
            result = cv.matchTemplate(screen_img, resized_template, method)

            # Determine the top 2 matches (best and 2nd best)
            num_matches = 2
            min_location = [0] * num_matches
            min_val = [0.0] * num_matches
            for i in range(num_matches):
                min_val[i], max_val, min_location[i], max_location = cv.minMaxLoc(result)
                val = result[min_location[i][1], min_location[i][0]]
                # Set the matched template area in the result matrix to worst value (1.0), so that it won't be considered in the next loop
                y_end = min(h_screen, min_location[i][1]+h_template//2+1)
                x_end = min(w_screen, min_location[i][0]+w_template//2+1)
                y_start = max(0, min_location[i][1]-h_template//2)
                x_start = max(0, min_location[i][0]-w_template//2)
                result[y_start:y_end, x_start:x_end] = 1.0

            # Calculate the click point
            if template_dpi > device_dpi:
                # Adjust click point if screen shot is scaled up as thats not the same click point as the device's current scale factor
                point = int((min_location[0][0] + pixel_offsets[0]) / self.upscale / scale_factor), int((min_location[0][1] + pixel_offsets[1]) / self.upscale / scale_factor)
            else:
                point = int((min_location[0][0] + pixel_offsets[0]) / self.upscale), int((min_location[0][1] + pixel_offsets[1]) / self.upscale)
            logging.debug(f"Matched template: {template} at scale: {scale} confidence: {(1 - min_val[0])}")

            # Save the new best match
            if (1 - min_val[1]) > next_best_match_val:
                next_best_match_val = 1 - min_val[1]
            if (1 - min_val[0]) > best_match[1]:
                best_match = (point, (1 - min_val[0]), next_best_match_val)

        logging.debug(f"Best Match: {best_match}")
        # Check if the match is above the threshold
        if best_match[1] < threshold:
            logging.debug(f"Match: {best_match[1]}, below threshold: {threshold}")
            template_basename = os.path.basename(template)
            self._save_screen("scaled_template_" + str(scale) + "_" + str(template_basename), resized_template)
            self._save_screen("capture_img_" + str(template_basename), screen_img)
            return (False, best_match[1], next_best_match_val)

        # Save the matched images for debugging
        template_basename = os.path.basename(template)
        self._save_screen("scaled_template_" + str(scale) + "_" + str(template_basename), resized_template)
        self._save_screen("capture_img_" + str(template_basename), screen_img)

        # return the click point and the confidence of the match
        return best_match

    # Check for a template match in a screenshot. Returns True if any template is found, False if not.
    def check(self, templates, screenshot, threshold=None, method=default_template_method, scale_factors=None, edge_detect_thresholds=None):
        if len(templates) == 0:
            raise Exception("Template not found")
        for t in templates:
            point, confidence, fail_level = self.get_point(t, screenshot, threshold, method, scale_factors, edge_detect_thresholds=edge_detect_thresholds)
            if point != False:
                return True
        return False
