import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type ChangeEvent, type FormEvent } from "react";

import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from "@khetibadi/ui";
import type {
  ChatSession,
  CropRecommendationRequest,
  FarmCreateRequest,
  FertilizerRecommendationRequest,
  MarketPrice,
  PriceAlertDirection,
  YieldPredictionRequest,
} from "@khetibadi/types";

import { apiBaseURL, chatApi, farmApi, marketApi, mlApi, visionApi } from "../lib/api";
import { queryClient } from "../lib/query-client";
import { EmptyState, ErrorState, LoadingGrid } from "../components/states";
import { getAccessToken, useAuthUser } from "../store/auth-store";

const farmKeys = {
  all: ["farms"] as const,
  list: () => [...farmKeys.all, "list"] as const,
  samples: (farmId: string) => [...farmKeys.all, farmId, "soil-samples"] as const,
};

const marketKeys = {
  all: ["market"] as const,
  prices: () => [...marketKeys.all, "prices"] as const,
  commodities: () => [...marketKeys.all, "commodities"] as const,
  alerts: () => [...marketKeys.all, "alerts"] as const,
};

const chatKeys = {
  all: ["chat"] as const,
  sessions: () => [...chatKeys.all, "sessions"] as const,
  messages: (sessionId: string) => [...chatKeys.all, sessionId, "messages"] as const,
};

const defaultBoundary: FarmCreateRequest["boundary"] = {
  type: "Polygon",
  coordinates: [
    [
      [77.2, 28.6],
      [77.21, 28.6],
      [77.21, 28.61],
      [77.2, 28.61],
      [77.2, 28.6],
    ],
  ],
};

const cropDefaults: CropRecommendationRequest = {
  nitrogen: 90,
  phosphorus: 40,
  potassium: 55,
  temperature: 29,
  humidity: 72,
  ph: 6.6,
  rainfall: 180,
  season: "kharif",
  state: "punjab",
};

const cropOptions = ["rice", "wheat", "maize", "cotton", "sugarcane", "millet", "pulses"] as const;
const soilOptions = ["loamy", "clay", "sandy", "silty", "black", "red"] as const;
const seasonOptions = ["kharif", "rabi", "zaid", "whole year", "summer", "winter"] as const;
const stateOptions = [
  "punjab",
  "haryana",
  "uttar pradesh",
  "maharashtra",
  "karnataka",
  "west bengal",
  "keralam",
] as const;
const districtOptions = ["ludhiana", "pune", "kolhapur", "kozikhode", "burdwan", "davangere"] as const;
const directionOptions: readonly PriceAlertDirection[] = ["above", "below"];

export function DashboardHomePage() {
  const user = useAuthUser();
  const farms = useQuery({ queryKey: farmKeys.list(), queryFn: farmApi.list, staleTime: 10 * 60 * 1000 });
  const prices = useQuery({ queryKey: marketKeys.prices(), queryFn: marketApi.prices, staleTime: 5 * 60 * 1000 });
  const sessions = useQuery({ queryKey: chatKeys.sessions(), queryFn: chatApi.sessions });

  if (farms.isLoading || prices.isLoading || sessions.isLoading) {
    return <LoadingGrid />;
  }

  return (
    <section className="space-y-6">
      <div className="overflow-hidden rounded-[2rem] border border-[#d8c4a5] bg-[#2f5d3a] p-6 text-[#fffaf0] shadow-[0_22px_70px_rgba(47,93,58,0.18)] md:p-8">
        <p className="text-sm font-extrabold uppercase tracking-[0.24em] text-[#f3dfb4]">Khetibadi overview</p>
        <h1 className="mt-3 text-4xl font-black tracking-tight">Namaste, {user?.name ?? "Farmer"}</h1>
        <p className="mt-3 max-w-2xl text-[#efe3d1]">A single mitti-green workspace for farms, crop advisory, plant health, mandi prices, and AI guidance.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Farms" value={farms.data?.length ?? 0} />
        <StatCard label="Market rows" value={prices.data?.length ?? 0} />
        <StatCard label="Chat sessions" value={sessions.data?.length ?? 0} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Market highlights</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(prices.data ?? []).slice(0, 3).map((price) => (
              <div className="flex items-center justify-between rounded-2xl border border-[#e7d8bf] bg-[#f7eddc] p-4" key={price.id}>
                <div>
                  <p className="font-bold capitalize text-[#2d2217]">{price.commodity}</p>
                  <p className="text-sm text-[#7a6548]">{price.market}, {price.state}</p>
                </div>
                <Badge tone="green">₹{price.modal_price}/{price.unit}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Next actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-[#6d5a40]">
            <p>Create a farm boundary, add a soil sample, run crop recommendation, scan a plant image, and ask the AI assistant for localized guidance.</p>
            <p>The dashboard uses only the public auth gateway configured by <code>VITE_API_BASE_URL</code>.</p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

export function FarmMapPage() {
  const farms = useQuery({ queryKey: farmKeys.list(), queryFn: farmApi.list, staleTime: 10 * 60 * 1000 });
  const [form, setForm] = useState<FarmCreateRequest>({
    name: "",
    crop: "wheat",
    soil_type: "loamy",
    area_hectares: 2.5,
    boundary: defaultBoundary,
  });
  const createFarm = useMutation({
    mutationFn: farmApi.create,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: farmKeys.all });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    createFarm.mutate(form);
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Card>
        <CardHeader>
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-[#b87924]">My farms</p>
          <CardTitle>Add farm</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <TextField label="Name" placeholder="North field" value={form.name} onChange={(value) => { setForm({ ...form, name: value }); }} />
            <SelectField label="Crop" options={cropOptions} value={form.crop} onChange={(value) => { setForm({ ...form, crop: value }); }} />
            <SelectField label="Soil type" options={soilOptions} value={form.soil_type} onChange={(value) => { setForm({ ...form, soil_type: value }); }} />
            <NumberField label="Area hectares" value={form.area_hectares} onChange={(value) => { setForm({ ...form, area_hectares: value }); }} />
            {createFarm.error ? <p className="text-sm font-semibold text-[#8a2f22]">Unable to create farm.</p> : null}
            <Button loading={createFarm.isPending} type="submit">Create farm</Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Farm boundaries</CardTitle>
        </CardHeader>
        <CardContent>
          {farms.isLoading ? <LoadingGrid /> : null}
          {farms.error ? <ErrorState title="Farm loading failed" message="Check the gateway and HMAC service wiring." /> : null}
          {farms.data?.length === 0 ? <EmptyState title="No farms yet" description="Create your first farm to see it here." /> : null}
          <div className="grid gap-3">
            {(farms.data ?? []).map((farm) => (
              <div className="rounded-[1.4rem] border border-[#d8c4a5] bg-[#f7eddc] p-4 shadow-sm" key={farm.id}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-bold text-[#2d2217]">{farm.name}</h3>
                    <p className="text-sm text-[#7a6548]">{farm.crop} · {farm.soil_type} · {farm.area_hectares} ha</p>
                  </div>
                  <Badge tone="green">active</Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

export function CropAdvisorPage() {
  const [features, setFeatures] = useState<CropRecommendationRequest>(cropDefaults);
  const [crop, setCrop] = useState<string>("wheat");
  const [soilType, setSoilType] = useState<string>("loamy");
  const [areaHectares, setAreaHectares] = useState<number>(2.5);
  const [district, setDistrict] = useState<string>("ludhiana");
  const recommend = useMutation({ mutationFn: mlApi.recommend });
  const yieldPredict = useMutation({ mutationFn: mlApi.yield });
  const fertilizer = useMutation({ mutationFn: mlApi.fertilizer });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    recommend.mutate(features);
    const yieldRequest: YieldPredictionRequest = { ...features, crop, area_hectares: areaHectares, district };
    yieldPredict.mutate(yieldRequest);
    const fertilizerRequest: FertilizerRecommendationRequest = { ...features, crop, soil_type: soilType };
    fertilizer.mutate(fertilizerRequest);
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
      <Card>
        <CardHeader>
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-[#b87924]">Soil to seed</p>
          <CardTitle>Crop advisor</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <SelectField label="Crop for yield/fertilizer" options={cropOptions} value={crop} onChange={setCrop} />
            <SelectField label="Soil type" options={soilOptions} value={soilType} onChange={setSoilType} />
            <NumberField label="Area hectares" value={areaHectares} onChange={setAreaHectares} />
            <SelectField label="District" options={districtOptions} value={district} onChange={setDistrict} />
            <FeatureFields value={features} onChange={setFeatures} />
            <Button loading={recommend.isPending || yieldPredict.isPending || fertilizer.isPending} type="submit">Run advisory</Button>
          </form>
        </CardContent>
      </Card>
      <div className="grid gap-4">
        <ResultCard title="Crop recommendation" body={recommend.data ? `${recommend.data.crop} (${Math.round(recommend.data.confidence * 100)}%)` : "Submit soil and climate data."} />
        <ResultCard title="Yield forecast" body={yieldPredict.data ? `${yieldPredict.data.predicted_yield_tonnes} tonnes total` : "Waiting for forecast."} />
        <ResultCard title="Fertilizer plan" body={fertilizer.data ? `N ${fertilizer.data.nitrogen_kg_per_ha} / P ${fertilizer.data.phosphorus_kg_per_ha} / K ${fertilizer.data.potassium_kg_per_ha} kg/ha` : "Waiting for plan."} />
      </div>
    </section>
  );
}

export function DiseaseScanPage() {
  const [file, setFile] = useState<File | null>(null);
  const detect = useMutation({ mutationFn: visionApi.detect });
  const fileSelected = file !== null;

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (file !== null) {
      detect.mutate(file);
    }
  }

  function updateFile(event: ChangeEvent<HTMLInputElement>): void {
    setFile(event.target.files?.[0] ?? null);
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Card>
        <CardHeader>
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-[#b87924]">Plant health</p>
          <CardTitle>Disease scan</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <Label>Leaf image</Label>
            <Input accept="image/png,image/jpeg" onChange={updateFile} required type="file" />
            {fileSelected ? <p className="text-sm font-semibold text-[#2f5d3a]">Selected {file.name}</p> : null}
            {detect.error ? <p className="text-sm font-semibold text-[#8a2f22]">Scan failed. Upload a JPEG or PNG at least 64×64.</p> : null}
            <Button disabled={!fileSelected} loading={detect.isPending} type="submit">Scan plant</Button>
          </form>
        </CardContent>
      </Card>
      <ResultCard
        title="Detection result"
        body={detect.isPending ? "Scanning the uploaded leaf image…" : detect.data ? `${detect.data.disease} · ${Math.round(detect.data.confidence * 100)}% confidence · ${detect.data.model_mode}` : "Upload a clear crop-leaf image for disease detection."}
      />
    </section>
  );
}

export function MarketPricesPage() {
  const prices = useQuery({ queryKey: marketKeys.prices(), queryFn: marketApi.prices, staleTime: 5 * 60 * 1000 });
  const alerts = useQuery({ queryKey: marketKeys.alerts(), queryFn: marketApi.alerts });
  const [alert, setAlert] = useState({ commodity: "wheat", state: "punjab", market: "ludhiana", direction: "above" as PriceAlertDirection, target_price: 2500 });
  const priceRows = prices.data ?? [];
  const commodityOptions = uniqueMarketOptions(priceRows, "commodity", ["wheat", "rice", "maize", "mustard"]);
  const alertStateOptions = uniqueMarketOptions(priceRows, "state", stateOptions);
  const marketOptions = uniqueMarketOptions(priceRows, "market", ["ludhiana", "mukkom market", "burdwan"]);
  const createAlert = useMutation({
    mutationFn: marketApi.createAlert,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: marketKeys.alerts() }),
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    createAlert.mutate(alert);
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader><p className="text-xs font-extrabold uppercase tracking-[0.2em] text-[#b87924]">Mandi watch</p><CardTitle>Market prices</CardTitle></CardHeader>
          <CardContent>
            {prices.error ? <ErrorState title="Prices unavailable" message="Market service did not return prices." /> : <PriceTable prices={priceRows} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Create alert</CardTitle></CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submit}>
              <SelectField label="Commodity" options={commodityOptions} value={alert.commodity} onChange={(commodity) => { setAlert({ ...alert, commodity }); }} />
              <SelectField label="State" options={alertStateOptions} value={alert.state} onChange={(state) => { setAlert({ ...alert, state }); }} />
              <SelectField label="Market" options={marketOptions} value={alert.market} onChange={(market) => { setAlert({ ...alert, market }); }} />
              <SelectField label="Direction" options={directionOptions} value={alert.direction} onChange={(direction) => { setAlert({ ...alert, direction: direction as PriceAlertDirection }); }} />
              <NumberField label="Target price" value={alert.target_price} onChange={(targetPrice) => { setAlert({ ...alert, target_price: targetPrice }); }} />
              <Button loading={createAlert.isPending} type="submit">Save alert</Button>
            </form>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>My alerts</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {(alerts.data ?? []).map((item) => (
            <p className="rounded-2xl border border-[#e7d8bf] bg-[#f7eddc] p-3 text-sm text-[#5f4a33]" key={item.id}>{item.commodity} {item.direction} ₹{item.target_price}</p>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}

export function AIAssistantPage() {
  const sessions = useQuery({ queryKey: chatKeys.sessions(), queryFn: chatApi.sessions });
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const createSession = useMutation({
    mutationFn: chatApi.createSession,
    onSuccess: async (session) => {
      setActiveSession(session.id);
      await queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
  const messages = useQuery({
    queryKey: chatKeys.messages(activeSession ?? "none"),
    queryFn: () => (activeSession === null ? Promise.resolve([]) : chatApi.messages(activeSession)),
    enabled: activeSession !== null,
  });
  const [streamText, setStreamText] = useState("");
  const [streamError, setStreamError] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  async function ensureSession(): Promise<ChatSession> {
    if (activeSession !== null) {
      const session = sessions.data?.find((item) => item.id === activeSession);
      if (session !== undefined) {
        return session;
      }
    }
    return await chatApi.createSession({ title: "Field advisory" });
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setStreamText("");
    setStreamError("");
    setIsStreaming(true);
    const session = await ensureSession();
    setActiveSession(session.id);
    try {
      const token = getAccessToken();
      const headers = new Headers({ "Content-Type": "application/json" });
      if (token !== null) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      const response = await fetch(`${apiBaseURL()}/ai/chat/sessions/${session.id}/messages`, {
        body: JSON.stringify({ message, language: "en" }),
        credentials: "include",
        headers,
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Chat request failed with HTTP ${response.status}`);
      }
      await readChatStream(response, {
        onDone: () => { setMessage(""); },
        onError: (error) => { setStreamError(error); },
        onToken: (token) => { setStreamText((current) => `${current}${token}`); },
      });
      await queryClient.invalidateQueries({ queryKey: chatKeys.messages(session.id) });
      await queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
      setStreamText("");
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : "Chat request failed");
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[300px_1fr]">
      <Card>
        <CardHeader><CardTitle>Sessions</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <Button onClick={() => { createSession.mutate({ title: "Field advisory" }); }} variant="secondary">New chat</Button>
          {(sessions.data ?? []).map((session) => (
            <button className="block w-full rounded-2xl border border-[#d8c4a5] bg-[#fffaf0] px-3 py-2 text-left text-sm font-semibold text-[#5f4a33] hover:bg-[#f7eddc]" key={session.id} onClick={() => { setActiveSession(session.id); }} type="button">
              {session.title}
            </button>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>AI assistant</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="max-h-80 space-y-3 overflow-auto rounded-[1.5rem] border border-[#e7d8bf] bg-[#f7eddc] p-4">
            {(messages.data ?? []).map((item) => (
              <p className="rounded-2xl bg-[#fffaf0] p-3 text-sm text-[#5f4a33] shadow-sm" key={item.id}><strong>{item.role}:</strong> {item.content}</p>
            ))}
            {streamText !== "" ? <p className="whitespace-pre-wrap rounded-2xl bg-[#e3eadb] p-3 text-sm leading-6 text-[#2f5d3a]"><strong>assistant:</strong> {streamText}</p> : null}
            {streamError !== "" ? <p className="rounded-2xl bg-[#f5d7ce] p-3 text-sm font-semibold text-[#8a2f22]">{streamError}</p> : null}
          </div>
          <form className="space-y-3" onSubmit={(event) => { void submit(event); }}>
            <Textarea placeholder="Ask about irrigation, pests, crop planning, or mandi decisions." value={message} onChange={(event) => { setMessage(event.target.value); }} />
            <Button disabled={message.trim() === "" || isStreaming} loading={isStreaming} type="submit">{isStreaming ? "Thinking…" : "Send message"}</Button>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}

export function SettingsPage() {
  return (
    <Card>
      <CardHeader><CardTitle>Settings</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm leading-6 text-[#6d5a40]">
        <p>Memory-only access tokens are restored by the gateway refresh cookie after browser reloads.</p>
        <p>Public API origin: <code>{apiBaseURL()}</code></p>
      </CardContent>
    </Card>
  );
}

type ChatStreamHandlers = {
  onDone: () => void;
  onError: (error: string) => void;
  onToken: (token: string) => void;
};

async function readChatStream(response: Response, handlers: ChatStreamHandlers): Promise<void> {
  if (response.body === null) {
    parseChatStreamText(await response.text(), handlers);
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const split = buffer.split("\n\n");
      buffer = split.pop() ?? "";
      for (const block of split) {
        handleChatStreamBlock(block, handlers);
      }
    }
    buffer += decoder.decode();
    if (buffer.trim() !== "") {
      handleChatStreamBlock(buffer, handlers);
    }
  } finally {
    reader.releaseLock();
  }
}

function parseChatStreamText(text: string, handlers: ChatStreamHandlers): void {
  for (const block of text.split("\n\n")) {
    if (block.trim() !== "") {
      handleChatStreamBlock(block, handlers);
    }
  }
}

function handleChatStreamBlock(block: string, handlers: ChatStreamHandlers): void {
  const lines = block.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event: "));
  const dataLine = lines.find((line) => line.startsWith("data: "));
  if (eventLine === undefined || dataLine === undefined) {
    return;
  }
  const event = eventLine.replace("event: ", "").trim();
  const data = parseStreamPayload(dataLine.replace("data: ", ""));
  if (event === "token") {
    const token = typeof data.token === "string" ? data.token : "";
    if (token !== "") {
      handlers.onToken(token);
    }
    return;
  }
  if (event === "done") {
    handlers.onDone();
    return;
  }
  if (event === "error") {
    const error = typeof data.error === "string" ? data.error : "chat_stream_failed";
    handlers.onError(error);
  }
}

function parseStreamPayload(value: string): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return {};
  }
  return {};
}

function StatCard({ label, value }: { label: string; value: number }) {
  return <Card><CardContent><p className="text-sm font-semibold text-[#7a6548]">{label}</p><p className="mt-2 text-4xl font-black text-[#2f5d3a]">{value}</p></CardContent></Card>;
}

function ResultCard({ body, title }: { body: string; title: string }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent><p className="text-[#5f4a33]">{body}</p></CardContent></Card>;
}

function TextField({ label, onChange, placeholder, value }: { label: string; onChange: (value: string) => void; placeholder?: string; value: string }) {
  return <div className="space-y-2"><Label>{label}</Label><Input placeholder={placeholder} value={value} onChange={(event) => { onChange(event.target.value); }} required /></div>;
}

function NumberField({ label, onChange, value }: { label: string; onChange: (value: number) => void; value: number }) {
  return <div className="space-y-2"><Label>{label}</Label><Input type="number" value={value} onChange={(event) => { onChange(Number(event.target.value)); }} required /></div>;
}

function SelectField({ label, onChange, options, value }: { label: string; onChange: (value: string) => void; options: readonly string[]; value: string }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <select className="w-full rounded-[1rem] border border-[#d8c4a5] bg-[#fffaf0] px-4 py-3 text-sm font-semibold text-[#3f2f1f] shadow-inner outline-none transition focus:border-[#2f5d3a] focus:ring-2 focus:ring-[#b87924]/25" required value={value} onChange={(event) => { onChange(event.target.value); }}>
        {options.map((option) => <option key={option} value={option}>{toTitleCase(option)}</option>)}
      </select>
    </div>
  );
}

function FeatureFields({ onChange, value }: { onChange: (value: CropRecommendationRequest) => void; value: CropRecommendationRequest }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {(["nitrogen", "phosphorus", "potassium", "temperature", "humidity", "ph", "rainfall"] as const).map((key) => (
        <NumberField key={key} label={key} value={value[key]} onChange={(next) => { onChange({ ...value, [key]: next }); }} />
      ))}
      <SelectField label="Season" options={seasonOptions} value={value.season} onChange={(season) => { onChange({ ...value, season }); }} />
      <SelectField label="State" options={stateOptions} value={value.state} onChange={(state) => { onChange({ ...value, state }); }} />
    </div>
  );
}

function uniqueMarketOptions(prices: MarketPrice[], key: "commodity" | "market" | "state", fallback: readonly string[]): string[] {
  const values = prices.map((price) => price[key].trim().toLowerCase()).filter((value) => value !== "");
  return Array.from(new Set([...values, ...fallback])).slice(0, 25);
}

function toTitleCase(value: string): string {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function PriceTable({ prices }: { prices: MarketPrice[] }) {
  if (prices.length === 0) {
    return <EmptyState title="No prices" description="Unknown commodities intentionally return an empty list." />;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow><TableHead>Commodity</TableHead><TableHead>Market</TableHead><TableHead>Min</TableHead><TableHead>Modal</TableHead><TableHead>Max</TableHead></TableRow>
      </TableHeader>
      <TableBody>
        {prices.map((price) => (
          <TableRow key={price.id}><TableCell className="capitalize">{price.commodity}</TableCell><TableCell>{price.market}</TableCell><TableCell>₹{price.min_price}</TableCell><TableCell>₹{price.modal_price}</TableCell><TableCell>₹{price.max_price}</TableCell></TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
