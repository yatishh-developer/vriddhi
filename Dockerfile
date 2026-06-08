# syntax=docker/dockerfile:1

FROM ghcr.io/cirruslabs/flutter:stable AS build

WORKDIR /app

COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get

COPY . .

ARG VABOS_API_BASE_URL=https://vriddhi-p7ax.onrender.com
ARG VABOS_ENVIRONMENT=production
ARG ENABLE_FIREBASE_AUTH=true
ARG FIREBASE_API_KEY=
ARG FIREBASE_APP_ID=
ARG FIREBASE_MESSAGING_SENDER_ID=
ARG FIREBASE_PROJECT_ID=
ARG FIREBASE_AUTH_DOMAIN=
ARG FIREBASE_STORAGE_BUCKET=

RUN flutter build web --release \
    --dart-define=VABOS_API_BASE_URL=${VABOS_API_BASE_URL} \
    --dart-define=VABOS_ENVIRONMENT=${VABOS_ENVIRONMENT} \
    --dart-define=ENABLE_FIREBASE_AUTH=${ENABLE_FIREBASE_AUTH} \
    --dart-define=FIREBASE_API_KEY=${FIREBASE_API_KEY} \
    --dart-define=FIREBASE_APP_ID=${FIREBASE_APP_ID} \
    --dart-define=FIREBASE_MESSAGING_SENDER_ID=${FIREBASE_MESSAGING_SENDER_ID} \
    --dart-define=FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID} \
    --dart-define=FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN} \
    --dart-define=FIREBASE_STORAGE_BUCKET=${FIREBASE_STORAGE_BUCKET}

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
