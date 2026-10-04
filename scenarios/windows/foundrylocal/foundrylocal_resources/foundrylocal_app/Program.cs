using Microsoft.AI.Foundry.Local;
using Microsoft.Extensions.Logging.Abstractions;

if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: FoundryLocalWorkload <setup|run|teardown> <model> [prompt]");
    return 1;
}

var operation = args[0];
var modelAlias = args[1];

await FoundryLocalManager.CreateAsync(
    new Configuration
    {
        AppName = "hobl_foundrylocal",
        LogLevel = Microsoft.AI.Foundry.Local.LogLevel.Information
    },
    NullLogger.Instance);

using var manager = FoundryLocalManager.Instance;
var catalog = await manager.GetCatalogAsync();
var model = await catalog.GetModelAsync(modelAlias)
    ?? throw new InvalidOperationException($"Model '{modelAlias}' was not found in the Foundry Local catalog.");

switch (operation)
{
    case "setup":
        Console.WriteLine($"Downloading model {model.Id}...");
        await model.DownloadAsync(progress =>
        {
            Console.Write($"\rDownload progress: {progress:F2}%");
            if (progress >= 100f)
            {
                Console.WriteLine();
            }
        });
        Console.WriteLine($"Model {model.Id} is ready.");
        break;

    case "run":
        if (args.Length < 3)
        {
            Console.Error.WriteLine("The run operation requires a prompt.");
            return 1;
        }

        await model.DownloadAsync();
        Console.WriteLine($"Loading model {model.Id}...");
        await model.LoadAsync();

        try
        {
            using var session = new ChatSession(model);
            using var request = new Request();
            request.AddItem(MessageItem.User(args[2]));

            using var response = await session.ProcessRequestAsync(request);
            var responseText = string.Join(
                Environment.NewLine,
                response
                    .OfType<MessageItem>()
                    .Where(message => message.IsSimpleText())
                    .Select(message => message.GetSimpleText()));

            if (string.IsNullOrWhiteSpace(responseText))
            {
                throw new InvalidOperationException("The model returned an empty response.");
            }

            Console.WriteLine(responseText);
        }
        finally
        {
            await model.UnloadAsync();
        }
        break;

    case "teardown":
        await model.RemoveFromCacheAsync();
        Console.WriteLine($"Removed model {model.Id} from the local cache.");
        break;

    default:
        Console.Error.WriteLine($"Unsupported operation '{operation}'.");
        return 1;
}

return 0;
