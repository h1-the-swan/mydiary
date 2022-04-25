import React, { useEffect } from "react";
import { SpotifyTrackHistoryRead, useReadSpotifyHistory } from "../api";
import { Table, TableColumnType } from "antd";

function SpotifyHistoryTable() {
  const { data: tracks, isLoading } = useReadSpotifyHistory(
    { limit: 5000 },
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
  useEffect(() => console.log(tracks), [tracks]);
  const columns: TableColumnType<SpotifyTrackHistoryRead>[] = [
    {
      title: "id",
      dataIndex: "id",
      key: "id",
      sorter: (a, b) => a.id - b.id,
    },
    {
      title: "Name",
      dataIndex: "track",
      key: "name",
      render: (track) => (
        <a href={track.uri} target="_blank" rel="noreferrer">
          {track.name}
        </a>
      ),
      sorter: (a, b) => a.track.name.localeCompare(b.track.name),
    },
    {
      title: "Artist",
      dataIndex: "track",
      key: "artist",
      render: (track) => track.artist_name,
      sorter: (a, b) => a.track.artist_name.localeCompare(b.track.artist_name),
    },
    {
      title: "Played At",
      dataIndex: "played_at",
      key: "played_at",
      render: (value: string) => {
        const dt = new Date(value + "Z");
        return dt.toLocaleString();
      },
      sorter: (a, b) =>
        new Date(b.played_at + "Z").getTime() -
        new Date(a.played_at + "Z").getTime(),
    },
    {
      title: "context_name",
      dataIndex: "context_name",
      key: "context_name",
      render: (value, record) => (
        <a href={record.context_uri} target="_blank" rel="noreferrer">
          {value}
        </a>
      ),
      sorter: true,
    },
  ];
  return isLoading ? (
    <span>Loading...</span>
  ) : (
    <Table
      dataSource={tracks}
      columns={columns}
      pagination={{ pageSize: 100 }}
    />
  );
}

const SpotifyHistory = () => {
  return (
    <main>
      <SpotifyHistoryTable />
    </main>
  );
};

export default SpotifyHistory;
