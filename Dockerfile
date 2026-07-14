# --- build stage ---
FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/skillbox .

# --- runtime stage ---
FROM gcr.io/distroless/static-debian12
COPY --from=build /out/skillbox /skillbox
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/skillbox"]
