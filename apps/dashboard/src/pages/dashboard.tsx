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
      <div>
        <p className="text-sm font-medium text-emerald-700">Welcome back</p>
        <h1 className="text-3xl font-bold text-slate-950">{user?.name ?? "Farmer"}</h1>
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
              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3" key={price.id}>
                <div>
                  <p className="font-semibold capitalize text-slate-900">{price.commodity}</p>
                  <p className="text-sm text-slate-500">{price.market}, {price.state}</p>
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
          <CardContent className="space-y-3 text-sm text-slate-600">
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
    name: "Demo Farm",
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
          <CardTitle>Add farm</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <TextField label="Name" value={form.name} onChange={(value) => { setForm({ ...form, name: value }); }} />
            <TextField label="Crop" value={form.crop} onChange={(value) => { setForm({ ...form, crop: value }); }} />
            <TextField label="Soil type" value={form.soil_type} onChange={(value) => { setForm({ ...form, soil_type: value }); }} />
            <NumberField label="Area hectares" value={form.area_hectares} onChange={(value) => { setForm({ ...form, area_hectares: value }); }} />
            {createFarm.error ? <p className="text-sm text-red-600">Unable to create farm.</p> : null}
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
              <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4" key={farm.id}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-slate-950">{farm.name}</h3>
                    <p className="text-sm text-slate-600">{farm.crop} · {farm.soil_type} · {farm.area_hectares} ha</p>
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
  const recommend = useMutation({ mutationFn: mlApi.recommend });
  const yieldPredict = useMutation({ mutationFn: mlApi.yield });
  const fertilizer = useMutation({ mutationFn: mlApi.fertilizer });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    recommend.mutate(features);
    const yieldRequest: YieldPredictionRequest = { ...features, crop, area_hectares: 2.5 };
    yieldPredict.mutate(yieldRequest);
    const fertilizerRequest: FertilizerRecommendationRequest = { ...features, crop, soil_type: "loamy" };
    fertilizer.mutate(fertilizerRequest);
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Crop advisor</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <TextField label="Crop for yield/fertilizer" value={crop} onChange={setCrop} />
            <FeatureFields value={features} onChange={setFeatures} />
            <Button loading={recommend.isPending || yieldPredict.isPending || fertilizer.isPending} type="submit">Run advisory</Button>
          </form>
        </CardContent>
      </Card>
      <div className="grid gap-4">
        <ResultCard title="Crop recommendation" body={recommend.data ? `${recommend.data.crop} (${Math.round(recommend.data.confidence * 100)}%)` : "Submit soil and climate data."} />
        <ResultCard title="Yield forecast" body={yieldPredict.data ? `${yieldPredict.data.estimated_total_tonnes} tonnes total` : "Waiting for forecast."} />
        <ResultCard title="Fertilizer plan" body={fertilizer.data ? `N ${fertilizer.data.nitrogen_kg_per_hectare} / P ${fertilizer.data.phosphorus_kg_per_hectare} / K ${fertilizer.data.potassium_kg_per_hectare} kg/ha` : "Waiting for plan."} />
      </div>
    </section>
  );
}

export function DiseaseScanPage() {
  const [file, setFile] = useState<File | null>(null);
  const detect = useMutation({ mutationFn: visionApi.detect });

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
          <CardTitle>Disease scan</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <Label>Leaf image</Label>
            <Input accept="image/png,image/jpeg" onChange={updateFile} required type="file" />
            {detect.error ? <p className="text-sm text-red-600">Scan failed. Upload a JPEG or PNG at least 64×64.</p> : null}
            <Button disabled={file === null} loading={detect.isPending} type="submit">Scan plant</Button>
          </form>
        </CardContent>
      </Card>
      <ResultCard
        title="Detection result"
        body={detect.data ? `${detect.data.disease} · ${Math.round(detect.data.confidence * 100)}% confidence · ${detect.data.model_mode}` : "Upload an image to run the local stub model."}
      />
    </section>
  );
}

export function MarketPricesPage() {
  const prices = useQuery({ queryKey: marketKeys.prices(), queryFn: marketApi.prices, staleTime: 5 * 60 * 1000 });
  const alerts = useQuery({ queryKey: marketKeys.alerts(), queryFn: marketApi.alerts });
  const [alert, setAlert] = useState({ commodity: "wheat", state: "punjab", market: "ludhiana", direction: "above" as PriceAlertDirection, target_price: 2500 });
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
          <CardHeader><CardTitle>Live market prices</CardTitle></CardHeader>
          <CardContent>
            {prices.error ? <ErrorState title="Prices unavailable" message="Market service did not return prices." /> : <PriceTable prices={prices.data ?? []} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Create alert</CardTitle></CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submit}>
              <TextField label="Commodity" value={alert.commodity} onChange={(commodity) => { setAlert({ ...alert, commodity }); }} />
              <TextField label="State" value={alert.state} onChange={(state) => { setAlert({ ...alert, state }); }} />
              <TextField label="Market" value={alert.market} onChange={(market) => { setAlert({ ...alert, market }); }} />
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
            <p className="rounded-xl bg-slate-50 p-3 text-sm" key={item.id}>{item.commodity} {item.direction} ₹{item.target_price}</p>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}

export function AIAssistantPage() {
  const sessions = useQuery({ queryKey: chatKeys.sessions(), queryFn: chatApi.sessions });
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [message, setMessage] = useState("What should I do for wheat crop this week?");
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
    const session = await ensureSession();
    setActiveSession(session.id);
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
    const body = await response.text();
    setStreamText(body.split("\n").filter((line) => line.startsWith("data: ")).map((line) => line.replace("data: ", "")).join("\n"));
    await queryClient.invalidateQueries({ queryKey: chatKeys.messages(session.id) });
    await queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[300px_1fr]">
      <Card>
        <CardHeader><CardTitle>Sessions</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <Button onClick={() => { createSession.mutate({ title: "Field advisory" }); }} variant="secondary">New chat</Button>
          {(sessions.data ?? []).map((session) => (
            <button className="block w-full rounded-xl border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50" key={session.id} onClick={() => { setActiveSession(session.id); }} type="button">
              {session.title}
            </button>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>AI assistant</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="max-h-80 space-y-3 overflow-auto rounded-2xl bg-slate-50 p-4">
            {(messages.data ?? []).map((item) => (
              <p className="rounded-xl bg-white p-3 text-sm shadow-sm" key={item.id}><strong>{item.role}:</strong> {item.content}</p>
            ))}
            {streamText !== "" ? <pre className="whitespace-pre-wrap rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">{streamText}</pre> : null}
          </div>
          <form className="space-y-3" onSubmit={(event) => { void submit(event); }}>
            <Textarea value={message} onChange={(event) => { setMessage(event.target.value); }} />
            <Button type="submit">Send message</Button>
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
      <CardContent className="space-y-3 text-sm text-slate-600">
        <p>Access tokens are held in memory only. Refresh is handled by the gateway cookie.</p>
        <p>Public API origin: <code>{apiBaseURL()}</code></p>
      </CardContent>
    </Card>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return <Card><CardContent><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-3xl font-bold text-slate-950">{value}</p></CardContent></Card>;
}

function ResultCard({ body, title }: { body: string; title: string }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent><p className="text-slate-700">{body}</p></CardContent></Card>;
}

function TextField({ label, onChange, value }: { label: string; onChange: (value: string) => void; value: string }) {
  return <div className="space-y-2"><Label>{label}</Label><Input value={value} onChange={(event) => { onChange(event.target.value); }} required /></div>;
}

function NumberField({ label, onChange, value }: { label: string; onChange: (value: number) => void; value: number }) {
  return <div className="space-y-2"><Label>{label}</Label><Input type="number" value={value} onChange={(event) => { onChange(Number(event.target.value)); }} required /></div>;
}

function FeatureFields({ onChange, value }: { onChange: (value: CropRecommendationRequest) => void; value: CropRecommendationRequest }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {(["nitrogen", "phosphorus", "potassium", "temperature", "humidity", "ph", "rainfall"] as const).map((key) => (
        <NumberField key={key} label={key} value={value[key]} onChange={(next) => { onChange({ ...value, [key]: next }); }} />
      ))}
      <TextField label="Season" value={value.season} onChange={(season) => { onChange({ ...value, season }); }} />
      <TextField label="State" value={value.state} onChange={(state) => { onChange({ ...value, state }); }} />
    </div>
  );
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
