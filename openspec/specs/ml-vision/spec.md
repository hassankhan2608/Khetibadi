# ML Vision Specification

## Purpose

Plant disease detection using a fine-tuned ResNet34 model. Accepts a plant leaf image, runs an OpenCV preprocessing pipeline, and returns the predicted disease class with confidence and an annotated image.

## Requirements

### Requirement: Disease Detection Inference

The system SHALL identify plant disease from a leaf image and return the disease class, confidence, and an annotated image.

#### Scenario: Successful detection — diseased leaf
- GIVEN a JPEG or PNG image of a tomato leaf with early blight
- WHEN `POST /ml/vision/detect` is called with the image as multipart/form-data
- THEN the response includes:
  - `disease`: "Tomato___Early_blight"
  - `plant`: "Tomato"
  - `confidence`: float (e.g. 0.92)
  - `is_healthy`: false
  - `annotated_image`: base64-encoded PNG with bounding box overlay
  - `recommendations`: list of treatment action strings

#### Scenario: Successful detection — healthy leaf
- GIVEN an image of a healthy apple leaf
- WHEN `POST /ml/vision/detect` is called
- THEN `is_healthy: true`, `disease: "Apple___healthy"`, and no bounding box is drawn on the annotated image

#### Scenario: Confidence below threshold
- GIVEN an image that does not clearly match any trained class (confidence < 0.60)
- WHEN the endpoint is called
- THEN `is_healthy: false` and `disease: "uncertain"` is returned
- AND `{"warning": "low_confidence", "confidence": <value>}` is included
- AND the annotated image is the original with no boxes

#### Scenario: Non-plant image
- GIVEN an uploaded image of a car or random object
- WHEN the endpoint is called
- THEN `confidence` is below 0.60 and `"uncertain"` is returned
- AND no crash occurs — the pipeline handles it gracefully

---

### Requirement: Background Removal Pre-Processing

Before the OpenCV pipeline runs, the system SHALL remove the image background using
`rembg` (U2Net model) to isolate the leaf from cluttered field backgrounds. Research
(Mohanty et al., MDPI Agriculture 2021) confirms that background removal improves
CNN classification accuracy on in-field images by reducing spurious feature activation.

#### Scenario: Background removed successfully

- GIVEN a field photograph with soil, other plants, or sky in the background
- WHEN the background removal step runs via `rembg.remove(image_bytes)`
- THEN the returned image has the background replaced with white pixels (RGB: 255,255,255)
- AND only the foreground leaf region retains its original colour values
- AND the background-removed image (PNG with alpha channel, then composited on white) is
  passed to the OpenCV pipeline

#### Scenario: Background removal fails (fallback)

- GIVEN `rembg` raises any exception (model load failure, memory error, etc.)
- WHEN the background removal step fails
- THEN the original image is passed directly to the OpenCV pipeline unchanged
- AND `"background_removed": false` is set in the response metadata
- AND the failure is logged at WARN level (no 5xx error to caller)

#### Scenario: Solid-colour background input

- GIVEN a studio/white-background image where background removal has no effect
- WHEN `rembg` processes the image
- THEN the output is visually identical to the input
- AND the pipeline proceeds normally

---

### Requirement: OpenCV Preprocessing Pipeline

After background removal, the image SHALL pass through a fixed OpenCV preprocessing pipeline.

#### Scenario: Pipeline steps in order
- GIVEN a background-removed RGB image (leaf on white)
- WHEN the preprocessing pipeline runs
- THEN steps execute in this order:
  1. Convert RGB → LAB color space
  2. Apply Otsu threshold on L channel to isolate leaf from white background
  3. Apply morphological operations (opening, then closing) to clean the mask
  4. Apply distance transform to find the centroid region
  5. Apply Canny edge detection to highlight lesion boundaries
  6. Find contours and draw bounding box around the largest contour
  7. Crop and resize the region to 128×128 pixels
  8. Normalize pixel values to [0.0, 1.0] using ImageNet mean/std
  9. Pass the tensor through ResNet34

#### Scenario: No contour found
- GIVEN an image where no contour of sufficient size is found (leaf is too small or background dominated)
- WHEN preprocessing runs
- THEN the full resized image (128×128) is used as fallback without cropping
- AND a `"fallback_resize": true` flag is included in the response

#### Scenario: Image too small
- GIVEN an image smaller than 64×64 pixels
- WHEN the endpoint is called
- THEN `400 Bad Request` with `{"error": "image_too_small", "min_size": "64x64"}`

---

### Requirement: Input Validation

The service SHALL validate image format, size, and dimensions before processing.

#### Scenario: Unsupported format
- GIVEN a file with `.gif` or `.bmp` extension
- WHEN uploaded to the detect endpoint
- THEN `415 Unsupported Media Type` is returned

#### Scenario: File too large
- GIVEN an image file larger than 10 MB
- WHEN uploaded
- THEN `413 Request Entity Too Large` is returned before any processing begins

#### Scenario: Corrupt image
- GIVEN a file with a `.jpg` extension but corrupted binary content
- WHEN OpenCV tries to decode it
- THEN `400 Bad Request` with `{"error": "image_decode_failed"}`

---

### Requirement: Supported Plant and Disease Classes

The model SHALL cover all 38 classes from the PlantVillage dataset.

#### Scenario: Supported classes list
- WHEN `GET /ml/vision/classes` is called
- THEN all 38 class names are returned, grouped by plant

#### Scenario: Plants covered
- The 14 plants covered include: Apple, Blueberry, Cherry, Corn, Grape, Orange, Peach, Bell Pepper, Potato, Raspberry, Soybean, Squash, Strawberry, Tomato

---

### Requirement: Async Processing for Large Batches

The system SHALL support submitting an image for async processing when synchronous latency is unacceptable.

#### Scenario: Async job submission
- GIVEN a high-resolution image (>2MB)
- WHEN `POST /ml/vision/detect/async` is called
- THEN a job ID is returned immediately with `202 Accepted`
- AND the image is enqueued in the `disease-scan` Asynq queue

#### Scenario: Async job polling
- GIVEN a job ID from a prior async submission
- WHEN `GET /ml/vision/detect/:job_id` is called
- THEN status is `"pending"`, `"processing"`, or `"complete"`
- AND when `"complete"`, the full detection result is included
