import {
  SendMessageCommand,
  type SendMessageCommandInput,
  type SendMessageCommandOutput,
  SQSClient,
} from "@aws-sdk/client-sqs";

const sqsClient = new SQSClient({});

export async function sendSqsMessage(
  input: SendMessageCommandInput,
): Promise<SendMessageCommandOutput> {
  return sqsClient.send(new SendMessageCommand(input));
}
