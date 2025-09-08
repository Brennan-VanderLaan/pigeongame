FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o pigeon-cni .

FROM alpine:latest
RUN apk --no-cache add ca-certificates curl vim tar
WORKDIR /root/

COPY --from=builder /app/pigeon-cni /pigeon-cni
COPY install_cni.sh /install.sh
RUN chmod +x /install.sh
RUN chmod +x /pigeon-cni

CMD ["/bin/sh", "-c", "/install.sh"]