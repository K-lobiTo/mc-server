# Makefile for managing the Minecraft server (Docker Compose)
# Usage: make <target>   e.g. `make up`, `make logs`, `make restart`

.PHONY: help up down restart stop start logs logs-mc logs-playit ps status \
        build pull console stats clean prune backup mods-ls update

# Default target: show help
help:
	@echo "Available commands:"
	@echo "  make up          - Start the server (detached)"
	@echo "  make down        - Stop and remove containers"
	@echo "  make restart     - Restart all containers"
	@echo "  make restart-mc  - Restart only the Minecraft container"
	@echo "  make stop        - Stop containers without removing them"
	@echo "  make start        - Start previously stopped containers"
	@echo "  make logs        - Follow logs for all services"
	@echo "  make logs-mc     - Follow logs for the Minecraft server only"
	@echo "  make logs-playit - Follow logs for the playit agent only"
	@echo "  make ps          - Show running containers"
	@echo "  make status      - Show container status + resource usage"
	@echo "  make stats       - Live CPU/RAM usage (docker stats)"
	@echo "  make console     - Attach to the Minecraft server console"
	@echo "  make pull        - Pull latest images"
	@echo "  make update      - Pull latest images and recreate containers"
	@echo "  make mods-ls     - List installed mods"
	@echo "  make backup      - Backup world data to a timestamped tar.gz"
	@echo "  make clean       - Remove stopped containers and dangling images"
	@echo "  make prune       - Deep clean: remove unused Docker data (careful)"

# --- Core lifecycle ---

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

restart-mc:
	docker compose restart minecraft

stop:
	docker compose stop

start:
	docker compose start

# --- Logs ---

logs:
	docker compose logs -f

logs-mc:
	docker compose logs -f minecraft

logs-playit:
	docker compose logs -f playit

# --- Status / monitoring ---

ps:
	docker compose ps

status:
	docker compose ps
	@echo ""
	docker stats --no-stream

stats:
	docker stats

# --- Interaction ---

# Attach to the Minecraft server console (Ctrl+P then Ctrl+Q to detach without stopping it)
console:
	docker attach mc-server

# --- Images / updates ---

pull:
	docker compose pull

update:
	docker compose pull
	docker compose up -d

# --- Mods ---

mods-ls:
	ls -la mc-data/mods/

# --- Backup ---

backup:
	@mkdir -p backups
	tar -czvf backups/world-backup-$$(date +%Y%m%d-%H%M%S).tar.gz mc-data/world
	@echo "Backup saved to backups/"

# --- Cleanup ---

clean:
	docker container prune -f
	docker image prune -f

prune:
	docker system prune -af --volumes
