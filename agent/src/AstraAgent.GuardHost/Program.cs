using AstraAgent.GuardHost;

// Started by Chrome / Edge / Firefox when the SAVIO extension connects. stdin/stdout carry the
// native messaging frames; nothing else may be written to stdout, or the browser drops the
// connection. Errors end the process quietly (exit 1) and the browser starts a fresh one.
try
{
    await NativeHost.RunAsync(Console.OpenStandardInput(), Console.OpenStandardOutput());
    return 0;
}
catch (Exception ex) when (ex is IOException or InvalidDataException)
{
    return 1;
}
