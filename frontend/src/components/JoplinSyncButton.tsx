import React, { useState } from "react";
import { useJoplinSync } from "../api";
import { Button } from "antd";

export default function JoplinSyncButton() {
  const [lastSync, setLastSync] = useState<Date>();
  const mutationJoplinSync = useJoplinSync({
    mutation: {
      onSuccess: () => setLastSync(new Date()),
    },
  });
  return (
    <div>
      <>
        {mutationJoplinSync.isError ? (
          <div>An error occurred: {mutationJoplinSync.error.message}</div>
        ) : null}

        {lastSync ? <p>{`Last Joplin sync: ${lastSync}`}</p> : null}
        <Button
          onClick={() => mutationJoplinSync.mutate()}
          loading={mutationJoplinSync.isLoading}
        >
          Sync
        </Button>
      </>
    </div>
  );
}
