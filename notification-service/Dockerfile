# ==========================
# Build
# ==========================
FROM maven:3.8.4-eclipse-temurin-17 AS build
WORKDIR /app

COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests

# ==========================
# Runtime (VERSION CORRIGÉE)
# ==========================
FROM eclipse-temurin:17-jdk-focal
WORKDIR /app

# Outils + Dapr (sans postgresql-client)
RUN apt-get update && apt-get install -y curl wget \
    && curl -fsSL https://raw.githubusercontent.com/dapr/cli/master/install/install.sh | /bin/bash \
    && wget -q https://github.com/dapr/dapr/releases/download/v1.12.0/daprd_linux_amd64.tar.gz \
    && tar -xzf daprd_linux_amd64.tar.gz \
    && mv daprd /usr/local/bin/ \
    && chmod +x /usr/local/bin/daprd \
    && rm daprd_linux_amd64.tar.gz \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# App
COPY --from=build /app/target/*.jar app.jar
COPY components /app/components

# Env
ENV APP_PORT=8082
ENV DAPR_HTTP_PORT=3500
ENV DAPR_GRPC_PORT=50001

EXPOSE 8082 3500 50001

# 🚀 DÉMARRAGE SIMPLIFIÉ (sans attente PostgreSQL)
CMD sh -c "daprd --app-id notification-service --app-port $APP_PORT --dapr-http-port $DAPR_HTTP_PORT --dapr-grpc-port $DAPR_GRPC_PORT --components-path /app/components & java -jar app.jar"