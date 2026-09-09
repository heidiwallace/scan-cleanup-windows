from scan_cleanup.workspace import WorkspaceManifest, create_workspace


def test_workspace_manifest_round_trip(tmp_path):
    workspace = create_workspace("volume", tmp_path)
    manifest = WorkspaceManifest(
        input_pdf="/input/volume.pdf",
        output_directory="/output",
        output_pdf="/output/volume_processed.pdf",
        source_dpi=300,
        output_dpi=1200,
        page_files=["volume-01.png"],
        expected_tiffs=["volume-01.tif"],
        scantailor_executable="/bin/scantailor-advanced",
    )

    manifest.save(workspace)

    assert WorkspaceManifest.load(workspace) == manifest
    assert (workspace / "input").is_dir()
    assert (workspace / "out").is_dir()
