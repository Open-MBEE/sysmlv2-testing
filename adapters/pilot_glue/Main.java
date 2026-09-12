package svt;

import org.omg.sysml.interactive.SysMLInteractive;
import org.omg.sysml.interactive.SysMLInteractiveResult;
import org.eclipse.xtext.validation.Issue;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Tiny headless glue over the Pilot Implementation's SysMLInteractive engine
 * (org.omg.sysml.interactive) -- no Eclipse Workbench, no Jupyter protocol.
 *
 * Usage: java -jar pilot-glue.jar <file1.sysml> [file2.sysml ...]
 * Env:   SYSML_LIBRARY_DIR - path to a sysml.library directory (the Pilot
 *        repo's own sysml.library/, or an equivalent OMG standard library
 *        checkout). Required for any input that imports the standard
 *        library (ScalarValues, Connections, etc).
 *
 * All files are concatenated into a single compilation unit and processed
 * in one SysMLInteractive.process(content, true) call -- matching how the
 * opensysml adapter feeds a multi-file TestCase to OpenSysML (one
 * concatenated content string), so a "does this multi-file model check
 * clean" comparison means the same thing across adapters. (An earlier
 * version processed each file as its own indexed resource in sequence;
 * confirmed both ways give the same verdict on every seeded test case, so
 * this is a consistency/simplicity choice, not a bug fix -- in particular,
 * the Pilot Implementation's "Must have at least two related elements"
 * error on end-feature-redefinition-explicit is the Pilot's own behavior
 * either way, not a harness artifact.)
 *
 * Prints "CLEAN" and exits 0 if there is no error-severity issue;
 * otherwise prints every issue and exits 1. This plain text is captured
 * verbatim by adapters/pilot_implementation.py as the RawResult.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            System.err.println("usage: java -jar pilot-glue.jar <file1.sysml> [file2.sysml ...]");
            System.exit(2);
        }

        SysMLInteractive instance = SysMLInteractive.createInstance();
        String libraryDir = System.getenv("SYSML_LIBRARY_DIR");
        if (libraryDir != null && !libraryDir.isEmpty()) {
            instance.loadLibrary(libraryDir);
        }

        StringBuilder content = new StringBuilder();
        for (String path : args) {
            content.append(new String(Files.readAllBytes(Paths.get(path))));
            content.append("\n");
        }

        List<String> lines = new ArrayList<>();
        boolean anyErrors;
        SysMLInteractiveResult result = instance.process(content.toString(), true);
        if (result.getException() != null) {
            anyErrors = true;
            lines.add("EXCEPTION: " + result.getException());
        } else {
            anyErrors = result.hasErrors();
            for (Issue issue : result.getIssues()) {
                lines.add(issue.getSeverity() + ": " + issue.getMessage()
                        + " (line " + issue.getLineNumber() + ")");
            }
        }

        System.out.println(anyErrors ? "ERRORS:" : "CLEAN");
        for (String line : lines) {
            System.out.println(line);
        }
        System.exit(anyErrors ? 1 : 0);
    }
}
