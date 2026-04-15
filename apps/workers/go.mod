module github.com/khetibadi/workers

go 1.26

require (
	github.com/gin-gonic/gin v1.12.0
	github.com/hibiken/asynq v0.26.0
	github.com/khetibadi/go-shared v0.0.0
)

replace github.com/khetibadi/go-shared => ../../packages/go-shared
