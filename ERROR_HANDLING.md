# Error Handling Guidelines

This project uses small asynchronous services connected through queues. Failures
can occur in individual services and should not crash the whole pipeline. The
`ErrorHandlerService` is responsible for logging such issues.

## Using `ErrorHandlerService`

Instantiate the service with a path to the log file and subscribe other services
to publish `ErrorEvent` messages. Any received error will be written to the log
with timestamp and severity. Example:

```python
error_service = ErrorHandlerService("errors.log")
other_service.subscribe(error_service, ["error"])
```

## Best Practices

* **Log everything** – ensure exceptions are caught and converted to
  `ErrorEvent` objects so the handler can record them.
* **Fail fast but gracefully** – propagate errors up the queue but avoid killing
  the event loop. Use `ErrorEvent` to notify the pipeline and let the handler
  decide how to react.
* **Separate concerns** – keep error handling logic isolated from business
  logic. Services should simply emit `ErrorEvent` when something unexpected
  happens.
* **Monitor the log** – review the log file regularly during development and
  production. Consider rotating or uploading logs if the application runs
  continuously.

These practices help keep the voice agent stable and make debugging easier.
