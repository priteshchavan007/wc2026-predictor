// Firebase Cloud Messaging service worker — handles daily reminder pushes
// when the app tab is closed or in the background.
importScripts('https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyDDuFB5d2R9gws79kX117mGHJvxZRIbwNk",
  authDomain: "wc2026-predictor-56ab2.firebaseapp.com",
  projectId: "wc2026-predictor-56ab2",
  messagingSenderId: "229291547598",
  appId: "1:229291547598:web:316de3c90a0bf8e9c5699f"
});

const messaging = firebase.messaging();

// Data-only messages are delivered here; we build the notification ourselves
// so it displays consistently and we control the click behaviour.
messaging.onBackgroundMessage(function (payload) {
  const data = payload.data || {};
  const title = data.title || '⚽ World Cup Predictor';
  const options = {
    body: data.body || 'Time to set your predictions for today!',
    tag: 'daily-reminder',
    renotify: true,
    data: { url: data.url || '/' }
  };
  self.registration.showNotification(title, options);
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (const client of list) {
        if ('focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(target);
    })
  );
});
