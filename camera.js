const video = document.getElementById("camera");
const message = document.getElementById("cameraMessage");
let cameraStream = null;

document.getElementById("startCamera")?.addEventListener("click", async () => {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = cameraStream;
    message.textContent = "Webcam preview is running. Vehicle detection is not enabled in this starter version.";
  } catch (error) {
    message.textContent = "Could not access the webcam. Check browser permission and camera connection.";
  }
});

document.getElementById("stopCamera")?.addEventListener("click", () => {
  if (cameraStream) cameraStream.getTracks().forEach(track => track.stop());
  cameraStream = null;
  video.srcObject = null;
  message.textContent = "Webcam stopped.";
});
