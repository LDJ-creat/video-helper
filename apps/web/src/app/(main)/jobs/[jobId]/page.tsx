import { JobPageClient } from "./JobPageClient";

interface PageProps {
    params: { jobId: string };
}

export default async function JobPage({ params }: PageProps) {
    // Next 16: params may be a Promise in some runtimes; await is safe either way.
    const { jobId } = await (params as unknown as Promise<{ jobId: string }>);
    return <JobPageClient jobId={jobId} />;
}
